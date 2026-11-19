import os as _os

# Anchor to this file's directory so the path resolves identically no
# matter where the python interpreter was invoked from. cron runs from
# $HOME and ad-hoc runs are often from /app/ — both used to silently
# pick up a stale pkl in the cwd instead of the project copy.
COOKIES_AFTER_LOGIN_PKL = _os.path.join(
    _os.path.dirname(_os.path.abspath(__file__)),
    'cookies_after_login.pkl',
)

ORIGIN_BASE_URL = 'https://8kuda4d.com'
BASE_URL = 'https://8kuda4d.com/mimin/'
ADMIN_AREA_PATH = '/mimin/adminarea'

# Mirrors blue-scraper's deposits schema but with bank_tujuan replacing info.
# Expected table (create in 'tele' database):
#   CREATE TABLE deposits (
#     id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
#     tanggal_isi_form DATETIME NOT NULL,
#     user_id VARCHAR(64) NOT NULL,
#     jumlah VARCHAR(32) NOT NULL,
#     bank_asal VARCHAR(128),
#     bank_tujuan VARCHAR(128),
#     is_confirmed TINYINT(1) DEFAULT 0,
#     confirmed_by VARCHAR(64),
#     remarks VARCHAR(255),
#     created_at DATETIME NOT NULL,
#     updated_at DATETIME NOT NULL,
#     UNIQUE KEY uq_deposit (tanggal_isi_form, user_id, jumlah, bank_asal, bank_tujuan)
#   );
# tanggal must already be ISO ("YYYY-MM-DD HH:MM:SS") — see deposits.py
# parse_pending_html which converts the scraped "23 Apr 2026 ..." form.
INSERT_DEPOSIT_QUERY = """
INSERT IGNORE INTO deposits
(tanggal_isi_form, user_id, jumlah, bank_asal, bank_tujuan, created_at, updated_at)
VALUES (%s, %s, %s, %s, %s,
CONVERT_TZ(UTC_TIMESTAMP(), '+00:00', '+07:00'),
CONVERT_TZ(UTC_TIMESTAMP(), '+00:00', '+07:00'))
"""

# Approve-queue lookup: rows flipped to is_confirmed=1 by some external
# process (mobile-scraper, admin UI, etc.). The scraper clicks through
# only these. 1-day window covers overnight carryover; the scraper acts
# only on rows currently visible in pending, so the broader window is
# harmless.
#
# CRITICAL: `remarks IS NULL` is what stops the auto-NA → reappear →
# false-approve race. Auto-NA writes remarks='NA' when a row vanishes
# from pending; if it ever shows up again (page-reload blip, double
# scraper, etc.) the row is `is_confirmed=1` in DB but explicitly NOT
# meant for approval. Without this filter the bot will approve real
# deposits with no mutasi backing them.
SELECT_CONFIRMED_DEPOSIT_QUERY_STARTING_FROM = """
SELECT tanggal_isi_form, user_id, jumlah, bank_asal, bank_tujuan
FROM deposits
WHERE is_confirmed=1 AND remarks IS NULL AND tanggal_isi_form>=%s
"""

# Auto-NA candidate lookup: unconfirmed rows in a 2-day Jakarta window
# whose remarks is still NULL. remarks IS NULL filters out rows already
# marked 'NA' so the sweep is idempotent.
SELECT_NOT_CONFIRMED_DEPOSIT_QUERY = """
SELECT id, tanggal_isi_form, user_id, jumlah, bank_asal, bank_tujuan
FROM deposits
WHERE is_confirmed=0
  AND (tanggal_isi_form>=%s AND tanggal_isi_form<=%s)
  AND remarks IS NULL
"""

# Per-user spec: when a deposit disappears from pending and we didn't
# approve it, set is_confirmed=1 and remarks='NA'. confirmed_by is
# intentionally left untouched — that column tracks the admin who
# actually approved a row, which is unknown for the auto-NA case.
UPDATE_DEPOSIT_QUERY_TO_AUTO_NA = """
UPDATE deposits
SET is_confirmed=1,
    remarks='NA',
    updated_at=CONVERT_TZ(UTC_TIMESTAMP(), '+00:00', '+07:00')
WHERE id IN ({})
"""
