#!/bin/bash
# GMGN Bot — installer (jalanin sekali)
set -e
cd "$(dirname "$0")"

echo "======================================"
echo "GMGN Auto-Create Bot — Installer"
echo "======================================"

# Cek Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 tidak ditemukan. Install dulu: apt install python3"
    exit 1
fi

# Install dependencies
echo ""
echo "[1/3] Install Python dependencies..."
pip3 install solders pynacl base58 2>&1 | tail -1 || pip install solders pynacl base58 2>&1 | tail -1

# Buat .env kalau belum ada
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[2/3] File .env dibuat — ISI 2CAPTCHA_API_KEY di sana!"
else
    echo "[2/3] File .env sudah ada (skip)"
fi

# Buat folder accounts
mkdir -p accounts
echo "[3/3] Folder accounts siap"

echo ""
echo "======================================"
echo "✅ INSTALL SELESAI!"
echo ""
echo "Langkah berikutnya:"
echo "  1. Edit file .env  → isi TWOCAPTCHA_API_KEY"
echo "  2. Jalankan:  ./run.sh   (atau: python3 gmgn_autocreate.py)"
echo "======================================"
