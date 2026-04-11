# 🚀 HFT Bot Platform v2.0 - Usage Guide

Selamat Datang di Pengoperasian HFT Bot Full Stack.

## 🛠 Instalasi Cepat
1. Clone repo: `git clone https://github.com/oyi77/HFT-Trading-Bot`
2. Install dependencies: `pip install rich fredapi yfinance pandas numpy`
3. Salin `.env`: `cp config.env.example .env` (Lengkapi datanya)

## 🕹 Cara Menjalankan
Cukup jalankan satu perintah ini:
```bash
python3 platform_launcher.py
```
Sistem akan otomatis menyalakan:
- **Telegram C2:** Kontrol bot dari HP.
- **Maintainer:** Bot yang ngetune strategi setiap hari.
- **Engine:** Monitor market & eksekusi signal.

## 📱 Perintah Telegram
- `/report` : Dapatkan analisa Alpha (Macro + Whale).
- `/status` : Cek apakah sistem sedang running atau pause.
- `/pause`  : Hentikan semua aktivitas trading.
- `/resume` : Mulai trading lagi.

## 📊 Monitoring (Dashboard)
Jika kamu di depan laptop dan mau gaya profesional, jalankan:
```bash
python3 tools/dashboard.py
```

## 🧠 Fitur Canggih
- **Macro Filter:** Bot tidak akan "Buy" jika DXY (Dollar) lagi menguat gila-gilaan.
- **Whale Tracker:** Bot mengikuti data akumulasi institusi besar.
- **Auto-Maintain:** Kalau performa turun, bot bakal backtest sendiri cari settingan baru.
