# PAY4D Bot Login

Utility untuk membuat ulang session cookie PAY4D melalui login manual di Chrome,
lalu menyimpan cookie tersebut sebagai `cookies_after_login.pkl`. File cookie ini
dipakai oleh scraper/bot lain agar bisa memakai session yang sudah login.

## Isi Repository

- `relogin.py` - membuka Chrome, menunggu login manual berhasil, menyimpan cookie,
  dan opsional mengirim cookie ke server.
- `driver_manager.py` - konfigurasi Selenium ChromeDriver.
- `base_page.py` - helper dasar untuk page object Selenium.
- `constants.py` - konstanta URL, path cookie, dan query database.
- `requirements.txt` - dependency Python.
- `DEPLOY.md` - catatan deployment server yang lebih detail.

File lokal seperti virtualenv, cookie pickle, profil Chrome, log, dan private key
tidak ikut di-commit karena sudah masuk `.gitignore`.

## Setup dari Repo Baru

Clone repository:

```powershell
git clone https://github.com/<username>/<repo-name>.git
cd <repo-name>
```

Buat virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependency:

```powershell
pip install -r requirements.txt
```

Pastikan Google Chrome sudah ter-install. Jika Chrome tidak ada di lokasi default,
set variabel environment berikut:

```powershell
$env:PAY4D_CHROME_PATH = "C:\Path\To\chrome.exe"
```

## Cara Membuat Cookie Login

Jalankan di workstation/laptop yang punya tampilan browser, bukan server headless:

```powershell
python relogin.py --no-deploy
```

Chrome akan terbuka. Login manual sampai masuk halaman admin. Setelah berhasil,
script menyimpan:

```text
cookies_after_login.pkl
```

File ini sengaja tidak masuk Git karena berisi session login.

## Deploy Cookie ke Server

Secara default `relogin.py` bisa mengirim cookie ke server memakai `scp` dan `ssh`.
Konfigurasi default ada di `relogin.py`, dan bisa dioverride dengan environment:

```powershell
$env:PAY4D_DEPLOY_HOST = "your-server-ip"
$env:PAY4D_DEPLOY_USER = "ec2-user"
$env:PAY4D_DEPLOY_REMOTE_DIR = "/app/titi4d/blue-scraper-pay4d"
python relogin.py
```

Jika private key Anda bukan file `.pem` di root project (misalnya
`id_rsa`), arahkan script ke key tersebut:

```powershell
$env:PAY4D_SSH_KEY = "$env:USERPROFILE\Downloads\.ssh\id_rsa"
python relogin.py
```

Untuk menyimpan konfigurasi ini untuk PowerShell berikutnya:

```powershell
[Environment]::SetEnvironmentVariable(
  "PAY4D_SSH_KEY",
  "$env:USERPROFILE\Downloads\.ssh\id_rsa",
  "User"
)
```

Tutup lalu buka PowerShell kembali setelah menjalankan perintah penyimpanan.

Jika memakai private key `.pem`, simpan sementara di root project saat menjalankan
script. File `.pem` tidak akan ikut ke Git.

## Catatan Keamanan

Jangan commit file berikut:

- `.env`
- `*.pem`
- `cookies_*.pkl`
- `.chrome-manual-profile/`
- `chromedriver.log`

Kalau cookie atau key terlanjur ter-push, anggap bocor dan segera regenerate.

## Push Pertama ke GitHub

Setelah membuat repo kosong di GitHub:

```powershell
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<username>/<repo-name>.git
git push -u origin main
```
