#!/bin/bash
# GMGN Bot — jalankan (bikin 1 akun baru)
cd "$(dirname "$0")"

# Cek .env
if [ ! -f .env ]; then
    echo "❌ File .env belum ada."
    echo "   Jalankan: ./install.sh  (atau: cp .env.example .env lalu isi key)"
    exit 1
fi

# Load .env
set -a
. ./.env
set +a

echo "🚀 GMGN Auto-Create — mulai..."
python3 gmgn_autocreate.py
