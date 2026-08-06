# 🐸 GMGN Auto-Create Bot

Buat akun GMGN (gmgn.ai) secara otomatis **tanpa browser** — setiap kali dijalankan, bot membuat **1 akun baru** lengkap dengan wallet Solana, lalu **auto-follow wallet target**.

---

## 📋 Kebutuhan

| Kebutuhan | Keterangan |
|-----------|-----------|
| Python 3.10+ | Sudah termasuk di kebanyakan server |
| **2Captcha API Key** | Daftar gratis di [2captcha.com](https://2captcha.com), isi saldo ~$1 |
| Koneksi internet | Wajib |

> 💡 2Captcha dipakai buat solve reCAPTCHA GMGN. Saldo $1 cukup untuk ±8 akun.

---

## 🚀 Cara Pakai (3 Langkah)

### Langkah 1 — Install

```bash
cd gmgn-bot
./install.sh
```

Script ini akan:
- Install dependency Python (`solders`, `pynacl`, `base58`)
- Buat file `.env` (kalau belum ada)
- Buat folder `accounts/`

### Langkah 2 — Isi API Key

Edit file `.env`:

```bash
nano .env
```

Isi key 2captcha kamu:

```
TWOCAPTCHA_API_KEY=isi_key_kamu_disini
```

### Langkah 3 — Jalankan

```bash
./run.sh
```

Atau langsung:

```bash
python3 gmgn_autocreate.py
```

Setiap jalan = **1 akun baru** dibuat.

---

## 📁 Struktur Folder

```
gmgn-bot/
├── gmgn_autocreate.py   # Script utama (bot)
├── install.sh           # Installer (jalanin sekali)
├── run.sh               # Cara gampang buat run bot
├── .env.example         # Template konfigurasi
├── .env                 # [RAHASIA] API key kamu — jangan dibagikan
└── accounts/
    └── gmgn_accounts.json  # [RAHASIA] Daftar akun + private keys
```

> ⚠️ **PENTING**: File `.env` dan folder `accounts/` berisi data sensitif.
> Jangan pernah commit ke Git atau bagikan ke siapa pun!

---

## ⚙️ Konfigurasi

Buka `gmgn_autocreate.py`, bagian **KONFIGURASI** di paling atas:

```python
# Wallet yang otomatis di-follow setiap akun baru
FOLLOW_TARGETS = {
    "sol": [
        "GV6UUmNxz2RpKxmNAPadYKb7uQpszwqQAu3qLJxVdC52",
        "AVAZvHLR2PcWpDf8BXY4rVxNHYRBytycHkcB5z5QNXYm",
    ],
}
```

Tambah/hapus wallet sesuai kebutuhan.

---

## 🧠 Cara Kerja Bot

```
1. Generate wallet Solana baru
2. Solve reCAPTCHA #1 (2captcha)
3. Initiate login ke GMGN → dapat session + nonce
4. Solve reCAPTCHA #2 + sign message (SIWE, base58)
5. Login → akun jadi + dapat access token
6. Auto-follow semua wallet di FOLLOW_TARGETS
7. Simpan akun ke accounts/gmgn_accounts.json
```

---

## 📊 Hasil

Semua akun tersimpan di `accounts/gmgn_accounts.json`:

```json
[
  {
    "address": "wallet_solana_baru...",
    "secret_b58": "private_key_wallet...",
    "access_token": "token_akses_gmgn...",
    "refresh_token": "token_refresh...",
    "expire_at": 1785991233,
    "followed": [
      {"chain": "sol", "address": "GV6UUm...", "ok": true}
    ]
  }
]
```

---

## ❓ Troubleshooting

| Masalah | Solusi |
|---------|--------|
| `ERROR_ZERO_BALANCE` | Saldo 2captcha habis — top up di 2captcha.com |
| `2CAPTCHA key tidak ditemukan` | Cek `.env` — pastikan `TWOCAPTCHA_API_KEY` terisi |
| `invalid login message` | Jarang terjadi — coba jalankan ulang (nonce expired) |
| Akun gagal dibuat | Cek saldo captcha, lalu run ulang |

---

## 🔒 Privasi

- Semua data lokal — tidak ada yang dikirim ke server lain selain GMGN & 2captcha
- Private key wallet tersimpan hanya di `accounts/gmgn_accounts.json`
- Bot **tidak menyimpan** data ke cloud
