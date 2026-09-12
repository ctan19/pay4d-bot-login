"""Generate cookies_after_login.pkl for the PAY4D scraper AND ship it to
the server.

Run this on a workstation (NOT the headless server). Opens a visible
Chrome with the most common WebDriver fingerprints suppressed so
Google's OAuth flow accepts a manual sign-in. After you complete the
'Continue with Google' flow (including 2FA if Google asks) and land on
/mimin/adminarea, this script saves the session cookies, scp's the pkl
to the server, and ssh's a sudo mv into the project dir.

Requirements on the workstation:
  - A `.pem` private key file in this project directory. The script
    globs for `*.pem` so the subordinate can drop their own key here
    without editing code.
  - `scp` and `ssh` on PATH (Windows 10+/11 have OpenSSH built in).

Skip deployment with `--no-deploy` if you just want the pkl locally.
"""
import glob
import os
import pickle
import subprocess
import sys
import time
import urllib.request
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from constants import (
    ADMIN_AREA_PATH,
    BASE_URL,
    COOKIES_AFTER_LOGIN_PKL,
)


# Deployment target — these are stable enough to hardcode. Override via
# env if you ever move the box or rename the project dir.
DEPLOY_HOST = os.getenv("PAY4D_DEPLOY_HOST", "52.220.167.86")
DEPLOY_USER = os.getenv("PAY4D_DEPLOY_USER", "ec2-user")
DEPLOY_REMOTE_DIR = os.getenv(
    "PAY4D_DEPLOY_REMOTE_DIR", "/app/titi4d/blue-scraper-pay4d")
DEPLOY_REMOTE_TMP = "/tmp/cookies_after_login.pkl"

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


# Google's WebDriver detection looks for static fingerprints (the
# --enable-automation switch, the AutomationControlled blink feature,
# navigator.webdriver === true). Suppressing all three is usually enough
# for a USER-DRIVEN OAuth — we're not trying to bypass behavioral
# fingerprinting, just static signals.
def _build_chrome_for_manual_login():
    log_path = os.path.join(_PROJECT_DIR, "chromedriver.log")
    debug_port = int(os.getenv("PAY4D_CHROME_DEBUG_PORT", "9222"))
    profile_dir = os.getenv(
        "PAY4D_CHROME_PROFILE_DIR",
        os.path.join(_PROJECT_DIR, ".chrome-manual-profile"),
    )

    chrome_path = _find_chrome_binary()
    if chrome_path is None:
        raise RuntimeError(
            "Chrome executable not found. Install Google Chrome or set "
            "PAY4D_CHROME_PATH to chrome.exe."
        )

    chrome_process = subprocess.Popen(
        [
            chrome_path,
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={profile_dir}",
            "--start-maximized",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ]
    )
    _wait_for_chrome_debugger(debug_port)

    # Attach to a normal Chrome process instead of letting ChromeDriver launch
    # Chrome with --enable-automation. Google commonly blocks that launch mode
    # during OAuth with "This browser or app may not be secure".
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")

    service = Service(
        executable_path=ChromeDriverManager().install(),
        service_args=["--verbose"],
        log_output=log_path,
    )

    driver = webdriver.Chrome(
        service=service,
        options=options,
    )

    # Hide the JS-level webdriver flag. Set BEFORE any page loads so
    # Google's inline detection scripts see undefined on first paint.
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source":
            "Object.defineProperty(navigator, 'webdriver', "
            "{get: () => undefined});"},
    )
    driver._pay4d_chrome_process = chrome_process
    return driver


def _find_chrome_binary() -> Optional[str]:
    env_path = os.getenv("PAY4D_CHROME_PATH")
    candidates = [
        env_path,
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _wait_for_chrome_debugger(port: int) -> None:
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.time() + 15
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except Exception as e:
            last_error = e
            time.sleep(0.25)
    raise RuntimeError(
        f"Chrome remote debugger did not start on port {port}: {last_error}"
    )


def _locate_ssh_key() -> Optional[str]:
    """Find an SSH private key to use for scp/ssh. Looks for any *.pem
    in the project root. Returns the absolute path if exactly one is
    present; returns None to fall back to the OS's default SSH config
    (~/.ssh/config + default keys). Raises only on the ambiguous case
    of multiple .pem files."""
    candidates = sorted(glob.glob(os.path.join(_PROJECT_DIR, "*.pem")))
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        return None
    raise RuntimeError(
        f"Multiple .pem files in {_PROJECT_DIR}: "
        f"{[os.path.basename(p) for p in candidates]}. Keep just one, "
        "or remove all of them to use your default ~/.ssh/config."
    )


def _deploy_pkl_to_server(pkl_path: str) -> None:
    """scp the pkl to /tmp then ssh-sudo-mv into the project dir.
    Sudo on the server is NOPASSWD for ec2-user, so the ssh call is
    non-interactive. Uses a project-local *.pem if present, otherwise
    falls back to the OS's default SSH config.
    Raises subprocess.CalledProcessError on failure."""
    key_path = _locate_ssh_key()
    remote_login = f"{DEPLOY_USER}@{DEPLOY_HOST}"
    remote_pkl = f"{DEPLOY_REMOTE_DIR.rstrip('/')}/cookies_after_login.pkl"

    # Common flags. -i is appended only when we found a project-local
    # key so that fallback users get their normal ~/.ssh/config behavior.
    common = ["-o", "StrictHostKeyChecking=accept-new"]
    if key_path:
        print(f"*** Using SSH key: {key_path}")
        common += ["-i", key_path]
    else:
        print("*** No project-local *.pem — using default SSH config")

    print(f"*** scp → {remote_login}:{DEPLOY_REMOTE_TMP}")
    subprocess.run(
        ["scp", *common, pkl_path, f"{remote_login}:{DEPLOY_REMOTE_TMP}"],
        check=True,
    )

    # Move into place + own as root so the cron-scheduled main.py (also
    # root) can read it. && chains so a failed mv aborts the chown.
    remote_cmd = (
        f"sudo mv {DEPLOY_REMOTE_TMP} {remote_pkl} && "
        f"sudo chown root:root {remote_pkl}"
    )
    print(f"*** ssh sudo mv → {remote_pkl}")
    subprocess.run(
        ["ssh", *common, remote_login, remote_cmd],
        check=True,
    )
    print("*** Deployed.")


def main():
    no_deploy = "--no-deploy" in sys.argv[1:]

    driver = _build_chrome_for_manual_login()

    print("=" * 70)
    print("PAY4D MANUAL OAUTH RE-LOGIN")
    print("=" * 70)
    print()
    print(f"Opening: {BASE_URL}")
    print()
    print("Steps in the Chrome window that just opened:")
    print("  1. Click 'Continue with Google'")
    print("  2. Sign in with the bot Google account")
    print("  3. Complete 2FA if Google asks")
    print("  4. Wait until you see the admin area")
    print()
    print("This script auto-detects admin-area arrival, saves cookies,")
    if no_deploy:
        print("and exits (--no-deploy: skipping server upload).")
    else:
        print("scp's the pkl to the server, and ssh-sudo-mv's it into place.")
    print("Don't close the Chrome window manually — let the script close it.")
    print()

    driver.get(BASE_URL)

    deadline = time.time() + 600  # 10-minute window for the manual flow
    saved_pkl_path = None
    while time.time() < deadline:
        try:
            url = driver.current_url
        except Exception as e:
            print(f"\nDriver error (did you close the window?): {e}")
            sys.exit(1)

        if ADMIN_AREA_PATH in url:
            cookies = driver.get_cookies()
            with open(COOKIES_AFTER_LOGIN_PKL, "wb") as f:
                pickle.dump(cookies, f)
            saved_pkl_path = os.path.abspath(COOKIES_AFTER_LOGIN_PKL)
            print()
            print(f"*** Detected admin area: {url}")
            print(f"*** Saved {len(cookies)} cookies to:")
            print(f"      {saved_pkl_path}")
            print()
            break
        time.sleep(2)

    # Close the browser before deployment so the user sees the scp/ssh
    # output instead of staring at the now-idle Chrome window.
    chrome_process = getattr(driver, "_pay4d_chrome_process", None)
    driver.quit()
    if chrome_process and chrome_process.poll() is None:
        chrome_process.terminate()

    if saved_pkl_path is None:
        print()
        print("Timed out after 10 minutes — re-run when you're ready to "
              "complete the flow.")
        sys.exit(1)

    if no_deploy:
        print("--no-deploy set; skipping server upload.")
        print(f"Manual upload command:")
        print(
            f"  scp -i <your.pem> {COOKIES_AFTER_LOGIN_PKL} "
            f"{DEPLOY_USER}@{DEPLOY_HOST}:{DEPLOY_REMOTE_TMP}")
        return

    try:
        _deploy_pkl_to_server(saved_pkl_path)
    except FileNotFoundError as e:
        print()
        print(f"ERROR: {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print()
        print(f"ERROR: deploy step failed ({e.cmd[0]} exited {e.returncode}).")
        print("The pkl was saved locally; you can fix the SSH issue and "
              "either re-run relogin.py or copy the file manually.")
        sys.exit(1)


if __name__ == "__main__":
    main()
