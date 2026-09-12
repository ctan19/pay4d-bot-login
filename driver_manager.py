import os
import sys

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def _should_run_headless() -> bool:
    """Auto-detect headless mode: Linux server with no DISPLAY → headless.
    Force explicitly with HEADLESS=1 (any platform), or disable with
    HEADLESS=0 (e.g., when X11 forwarding is configured)."""
    forced = os.getenv("HEADLESS", "").strip().lower()
    if forced in ("1", "true", "yes"):
        return True
    if forced in ("0", "false", "no"):
        return False
    return sys.platform.startswith("linux") and not os.getenv("DISPLAY")


class DriverManager:
    _driver = None

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            options = Options()
            options.add_experimental_option("detach", True)
            options.add_argument("--mute-audio")
            options.add_argument("--no-sandbox")
            options.add_argument("--start-maximized")
            # Stability flags — the admin SPA fires a lot of timers + jQuery
            # DOM rewrites; without these the tab crashes after ~20s.
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-renderer-backgrounding")
            if _should_run_headless():
                # 1920x1080 keeps the admin UI's responsive breakpoints
                # consistent with what the dev environment sees — some
                # buttons and menus collapse at narrower widths.
                options.add_argument("--headless=new")
                options.add_argument("--window-size=1920,1080")
            cls._driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options,
            )
        return cls._driver

    @classmethod
    def quit_driver(cls):
        if cls._driver:
            try:
                cls._driver.quit()
            except Exception:
                pass
            cls._driver = None

    @classmethod
    def restart_driver(cls):
        cls.quit_driver()
        return cls.get_driver()
