# PAY4D scraper deployment

Cookie-based auth (no Selenium OAuth — Google blocks WebDriver-controlled
Chrome from datacenter IPs). The session is created manually on a
workstation and shipped to the server as a pickle file. The cron-driven
scraper just loads cookies and runs.

## Server-side install (one-time)

Server: `52.220.167.86` (EC2). SSH as `ec2-user` with `blue.pem`. Project
files are owned by root, so server-side ops need `sudo`.

```bash
# As root (sudo -i or sudo each command)
mkdir -p /app/titi4d/blue-scraper-pay4d/logs
mkdir -p /var/log/scraper_monitor

# Clone the repo
cd /app/titi4d
git clone <repo-url> blue-scraper-pay4d
cd blue-scraper-pay4d

# Build the project venv (Python 3.9+; ddddocr is no longer required)
python3 -m venv myenv
./myenv/bin/pip install -r requirements.txt

# Install Chrome if missing
yum install -y https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
# (or apt install -y google-chrome-stable on Debian/Ubuntu)

# Install the failover monitor (lives in the sibling adhoc/ repo)
cp /path/to/adhoc/failover_monitor_pay4d.sh /opt/scraper_monitor/
chmod +x /opt/scraper_monitor/failover_monitor_pay4d.sh
# Verify the SCRAPERS line points at /app/titi4d/... not /app/pay4d/...
```

The EC2 IP must be whitelisted on buenatiti's admin allow-list — otherwise
`/mimin/` serves a 404 (we hit this in deploy). Coordinate with whoever
administers buenatiti.

## Generating cookies (`relogin.py`) — first run and renewals

Run on a **workstation** (Windows or Mac with a real display), NOT on the
server. The script opens a visible Chrome with anti-automation flags so
Google's OAuth flow accepts the manual sign-in, then automatically ships
the pkl to the server.

### One-time workstation setup

1. Make sure `ssh ec2-user@52.220.167.86` works from your shell. Two
   ways:
   - **Default SSH config**: your key lives at `~/.ssh/id_rsa` (or
     `~/.ssh/id_ed25519`, etc.) or is referenced in `~/.ssh/config`.
     Nothing more to do — `relogin.py` will use it automatically.
   - **Project-local key**: drop your `.pem` into the project root.
     The script globs for `*.pem` and passes it with `-i`. Keep exactly
     one `.pem` in the directory.
2. Ensure `scp` and `ssh` are on PATH. Windows 10+/11 ships OpenSSH by
   default; verify with `where scp` in PowerShell.

### Running

```powershell
# From the project dir on your workstation
.\myenv\Scripts\python.exe relogin.py
```

In the Chrome window that opens:
1. Click **Continue with Google**
2. Sign in with the bot Google account
3. Complete 2FA if Google asks
4. Wait — the script auto-detects `/mimin/adminarea`, saves the pkl, then
   scp's it to `/tmp/` on the server and `ssh sudo mv`'s it into
   `/app/titi4d/blue-scraper-pay4d/`. Sudo on the server is NOPASSWD for
   `ec2-user` so the deploy step is non-interactive.

Expected tail of the script's output:

```
*** Using SSH key: C:\...\your.pem
*** scp → ec2-user@52.220.167.86:/tmp/cookies_after_login.pkl
*** ssh sudo mv → /app/titi4d/blue-scraper-pay4d/cookies_after_login.pkl
*** Deployed.
```

Skip the upload step (e.g., to test the pkl locally first) with
`relogin.py --no-deploy`.

The cookie file is good until buenatiti's session expires (typically 30–90
days for OAuth-backed sessions). The signal you need to re-run `relogin.py`
is the failover monitor's stale-DB alert (Telegram).

## Cron block

Once the cookie is in place, install the cron lines (as root via
`sudo crontab -e`):

```cron
# PAY4D
0 */6 * * * /app/titi4d/blue-scraper-pay4d/myenv/bin/python -u /app/titi4d/blue-scraper-pay4d/main.py >> /app/titi4d/blue-scraper-pay4d/logs/pay4d_scrape_and_accept_`date +\%Y-\%m-\%d_\%H`.log 2>&1

# Maintenance Thursday (mirrors blue-scraper siblings)
30 2 * * 4 /app/titi4d/blue-scraper-pay4d/myenv/bin/python -u /app/titi4d/blue-scraper-pay4d/main.py >> /app/titi4d/blue-scraper-pay4d/logs/pay4d_scrape_and_accept_maintenance_`date +\%Y-\%m-\%d_\%H`.log 2>&1

# Pay4d fail-over (every 5 minutes)
5,10,15,20,25,30,35,40,45,50,55 * * * * /opt/scraper_monitor/failover_monitor_pay4d.sh
```

Each 6-hourly firing of `main.py` runs for ~6 hours (`MAX_RUN`), exits, and
the next firing starts a fresh driver. The failover monitor restarts the
scraper if it dies between firings or if DB freshness drops below 25 minutes
(LOW traffic threshold).

## Manual smoke test

```bash
sudo -u root /app/titi4d/blue-scraper-pay4d/myenv/bin/python /app/titi4d/blue-scraper-pay4d/main.py
```

Expected log lines:
- `Loaded N cookie(s) from cookies_after_login.pkl`
- `Cookie session restored; on admin area`
- `Deposit menu opened`
- `Connected to MySQL ...`
- `Pending deposits: N` (repeating every 10s)

Ctrl-C to stop.

## Troubleshooting

| Symptom | Diagnosis | Fix |
| --- | --- | --- |
| `Cookie file ... not found` | pkl never shipped | run `relogin.py`, scp, retry |
| `Cookie load did not result in admin-area session ... current_url=https://buenatiti.com/mimin/` | cookies expired | run `relogin.py`, scp, retry |
| `Login form never rendered ... current_url=https://buenatiti.com/404.shtml` | EC2 IP not whitelisted | ask buenatiti admin to whitelist `52.220.167.86` |
| `session not created: Chrome instance exited` | Chrome missing / OOM | `which google-chrome`; if missing install Chrome; if OOM check `free -m` |
| Failover monitor restarts the scraper repeatedly even though it's alive | LOW threshold (25 min) too aggressive for quiet periods | edit `failover_monitor_pay4d.sh`, change the `LOW` traffic_type to `LOWEST` (50-min threshold) |

## Architecture cheat sheet

- `main.py` — entrypoint: scrape pending list → INSERT → auto-NA stale rows → approve confirmed pending rows. 6-hour budget.
- `authentication.py` — cookie-only login (no captcha, no form). Fails clearly when cookies expired.
- `relogin.py` — workstation-side helper to regenerate `cookies_after_login.pkl` via manual OAuth.
- `deposits.py` — parses `var dataPending = [...]` JSON; auto-NA + confirmed-queue helpers.
- `accept.py` — `approve_selected(driver, deposit_ids)` ticks specific checkboxes by `tr#depositPending-<id>` and accepts the native confirm dialog.
- `driver_manager.py` — Chrome options + auto headless on Linux/no-DISPLAY.
- `constants.py` — DB schema, URLs, queries.
- `failover_monitor_pay4d.sh` — lives in sibling `adhoc/` repo; deployed to `/opt/scraper_monitor/`.
