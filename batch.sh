#!/bin/bash
# GMGN Bot — batch create (bikin banyak akun sekaligus)
#
# Cara pakai:
#   ./batch.sh 5              # bikin 5 akun (jeda default 30 detik)
#   ./batch.sh 10 --wait 60   # bikin 10 akun, jeda 60 detik
#   ./batch.sh 3 --no-wait    # bikin 3 akun tanpa jeda
#
# Sebelum jalan:
#   - Pastikan .env terisi (TWOCAPTCHA_API_KEY)
#   - Cek saldo 2captcha biar gak berhenti di tengah
#     curl -s "https://2captcha.com/res.php?key=KEY_LO&action=getbalance"

set -e
cd "$(dirname "$0")"

# ============ parse argumen ============
COUNT=5
WAIT=30
if [ -n "$1" ]; then COUNT="$1"; fi
if [ "$2" == "--wait" ] && [ -n "$3" ]; then WAIT="$3"; fi
if [ "$2" == "--no-wait" ]; then WAIT=0; fi

# ============ validasi ============
if [ ! -f .env ]; then
    echo "❌ File .env belum ada. Jalankan: ./install.sh"
    exit 1
fi
if ! echo "$COUNT" | grep -qE '^[0-9]+$' || [ "$COUNT" -lt 1 ]; then
    echo "❌ Jumlah harus angka positif (contoh: ./batch.sh 5)"
    exit 1
fi

# load .env (buat cek saldo)
set -a
. ./.env
set +a

# cek key 2captcha
if [ -z "$TWOCAPTCHA_API_KEY" ]; then
    echo "❌ TWOCAPTCHA_API_KEY kosong di .env"
    exit 1
fi

# cek saldo (opsional — kalau gagal tetap lanjut)
echo "ℹ️  Cek saldo 2captcha..."
BALANCE=$(curl -s --max-time 10 "https://2captcha.com/res.php?key=${TWOCAPTCHA_API_KEY}&action=getbalance" || echo "?")
echo "   Saldo: \$$BALANCE"

echo ""
echo "======================================"
echo "🚀 GMGN BATCH — bikin $COUNT akun"
echo "    Jeda antar akun: ${WAIT}s"
echo "======================================"
echo ""

SUCCESS=0
FAIL=0

for i in $(seq 1 "$COUNT"); do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "▶ Akun $i / $COUNT"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if python3 gmgn_autocreate.py; then
        SUCCESS=$((SUCCESS + 1))
    else
        FAIL=$((FAIL + 1))
    fi

    # jeda antar akun (kecuali akun terakhir)
    if [ "$i" -lt "$COUNT" ] && [ "$WAIT" -gt 0 ]; then
        echo ""
        echo "⏳ Jeda ${WAIT}s sebelum akun berikutnya..."
        sleep "$WAIT"
    fi
    echo ""
done

echo "======================================"
echo "✅ Selesai!"
echo "    Berhasil: $SUCCESS | Gagal: $FAIL"
echo "    Akun tersimpan di: accounts/gmgn_accounts.json"
echo "======================================"
