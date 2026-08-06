#!/usr/bin/env python3
"""
GMGN Auto-Create Bot
====================
Buat akun GMGN (gmgn.ai) otomatis tanpa browser.

Alur kerja:
  1. Generate wallet Solana baru
  2. Solve reCAPTCHA v2 (2captcha)
  3. Login/register via API GMGN (SIWE signature)
  4. Auto-follow wallet target
  5. Simpan akun ke accounts/gmgn_accounts.json

Cara pakai:
  - Isi 2CAPTCHA_API_KEY di file .env (lihat .env.example)
  - Jalankan: python3 gmgn_autocreate.py
  - Setiap jalan = bikin 1 akun baru

Dependencies:
  pip install solders pynacl base58
"""

import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import nacl.signing
from solders.keypair import Keypair

# =====================================================================
# KONFIGURASI — edit di sini kalau perlu
# =====================================================================

# Daftar wallet yang otomatis di-follow setiap akun baru dibuat.
# Format: { "chain": ["wallet_address_1", "wallet_address_2", ...] }
FOLLOW_TARGETS = {
    "sol": [
        "GV6UUmNxz2RpKxmNAPadYKb7uQpszwqQAu3qLJxVdC52",
        "AVAZvHLR2PcWpDf8BXY4rVxNHYRBytycHkcB5z5QNXYm",
    ],
}

# Berapa lama nunggu solusi captcha (detik)
CAPTCHA_TIMEOUT = 300

# =====================================================================
# JANGAN EDIT DI BAWAH INI (kecuali tahu apa yang dilakukan)
# =====================================================================

GMGN = "https://gmgn.ai"
SITEKEY_PAGE = "6Lf3pucqAAAAADbq3czpqDHRAD8j3kC-hcwwDG_T"          # captcha halaman
SITEKEY_REGISTER = "6LcrYOcqAAAAAPESxsGqz4NyUR0_cJs3YfCzuGOd"     # captcha register
TWOCAPTCHA_URL = "https://2captcha.com"
DEVICE_ID = "b59c3d76-5766-4fe1-b576-738fe500ece7"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
ACCOUNTS_PATH = os.path.join(BASE_DIR, "accounts", "gmgn_accounts.json")

UA = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36")


# ---------------------------------------------------------------- .env
def load_env():
    """Baca variabel dari file .env di folder bot, lalu environment."""
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as fh:
            for line in fh:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip().strip('"').strip("'")
    # fallback ke environment / ~/.hermes/.env (untuk penggunaan internal)
    hermes_env = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(hermes_env):
        with open(hermes_env) as fh:
            for line in fh:
                line = line.strip()
                if line and "=" in line:
                    k = line.split("=", 1)[0].strip()
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if k.startswith("TWOCAPTCHA_API_KEY") or k.startswith("CAPSOLVER_API_KEY"):
                        env.setdefault(k, v)
    return env


def load_captcha_keys():
    """Semua 2captcha key urut balance terbesar (yang positif dulu)."""
    env = load_env()
    keys = []
    for k in sorted(env.keys()):
        if k.startswith("TWOCAPTCHA_API_KEY") and env[k]:
            keys.append(env[k])
    keys += [os.environ.get("TWOCAPTCHA_API_KEY", "")]

    import subprocess
    with_balance = []
    for key in keys:
        if not key:
            continue
        try:
            out = subprocess.run(
                ["curl", "-s", "--max-time", "8", f"https://2captcha.com/res.php?key={key}&action=getbalance"],
                capture_output=True, text=True, timeout=12,
            )
            bal = out.stdout.strip()
            try:
                bal_f = float(bal)
                if bal_f > 0:
                    with_balance.append((bal_f, key))
            except ValueError:
                pass
        except Exception:
            pass
    with_balance.sort(reverse=True)  # balance terbesar dulu
    # dedupe (beberapa .env var bisa pegang key yang sama)
    seen = set()
    unique = []
    for _, k in with_balance:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    if unique:
        print(f"  Key 2captcha tersedia: {[k[:10] for k in unique]}")
    return unique


# ---------------------------------------------------------------- http
def api_path(path):
    return (f"{GMGN}{path}?device_id={DEVICE_ID}&fp_did=unknown"
            f"&client_id=gmgn_web_20260806-2992-8990b78&from_app=gmgn"
            f"&app_ver=20260806-2992-8990b78&tz_name=Asia/Jakarta")


def http_post(url, payload, headers=None):
    h = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": GMGN,
        "Referer": f"{GMGN}/?chain=sol",
        "sec-ch-ua": '"Chromium";v="148", "Quetta";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }
    if headers:
        h.update(headers)
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------- captcha
def solve_recaptcha(sitekey, action=None, page_url=f"{GMGN}/?chain=sol", retries=3):
    """Solve reCAPTCHA v2 checkbox via 2captcha. Returns token or None."""
    for attempt in range(1, retries + 1):
        if attempt > 1:
            print(f"  Retry captcha ({attempt}/{retries})...")
            time.sleep(3)
        token = _solve_recaptcha_once(sitekey, action, page_url)
        if token:
            return token
        print(f"  Captcha gagal (percobaan {attempt}/{retries})")
    return None


def _solve_recaptcha_once(sitekey, action=None, page_url=f"{GMGN}/?chain=sol"):
    """Coba 2captcha dulu, kalau gagal/lambat fallback ke Capsolver."""
    # 1. coba 2captcha (maks 40s tunggu, cepat fail kalau error)
    token = _solve_2captcha(sitekey, action, page_url, max_wait=60)
    if token:
        return token
    # 2. fallback capsolver
    print("  Fallback ke Capsolver...")
    return _solve_capsolver(sitekey, action, page_url)


def _solve_2captcha(sitekey, action=None, page_url=f"{GMGN}/?chain=sol", max_wait=120):
    """Coba SEMUA 2captcha key (urutan balance terbesar) sampai ada yang sukses."""
    keys = load_captcha_keys()
    if not keys:
        print("  2captcha key tidak ditemukan")
        return None
    for key in keys:
        print(f"  Coba 2captcha key {key[:12]}...")
        token = _solve_2captcha_with_key(key, sitekey, action, page_url, max_wait)
        if token:
            return token
        print(f"  Key {key[:12]}... gagal — coba key lain")
    return None


def _solve_2captcha_with_key(key, sitekey, action=None, page_url=f"{GMGN}/?chain=sol", max_wait=120):
    params = {
        "key": key,
        "method": "userrecaptcha",
        "googlekey": sitekey,
        "pageurl": page_url,
        "json": 1,
        # CATATAN: GMGN pakai reCAPTCHA v2 checkbox biasa (bukan enterprise).
        # Jangan tambahkan enterprise=1 — justru bikin workers gagal solve.
    }
    if action:
        params["action"] = action
    try:
        with urllib.request.urlopen(f"{TWOCAPTCHA_URL}/in.php?" + urllib.parse.urlencode(params), timeout=30) as r:
            resp = json.loads(r.read().decode())
        if resp.get("status") != 1:
            print("  2captcha error:", resp)
            return None
        task_id = resp["request"]
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(5)
            with urllib.request.urlopen(f"{TWOCAPTCHA_URL}/res.php?key={key}&action=get&id={task_id}&json=1", timeout=30) as r:
                resp = json.loads(r.read().decode())
            if resp.get("status") == 1:
                return resp["request"]
            if "CAPCHA_NOT_READY" not in str(resp.get("request", "")):
                print("  2captcha error:", resp)
                return None
        return None
    except Exception as e:
        print("  2captcha error:", e)
        return None


def _solve_capsolver(sitekey, action=None, page_url=f"{GMGN}/?chain=sol", max_wait=180):
    """Solve reCAPTCHA v2 via Capsolver (fallback provider)."""
    env = load_env()
    keys = [env[k] for k in sorted(env.keys())
            if k.startswith("CAPSOLVER_API_KEY") and env[k]]
    if not keys:
        print("  Capsolver key tidak ada di .env — skip")
        return None

    # pilih key dengan balance TERBESAR (> 0)
    import subprocess
    client_key = None
    best_balance = 0
    for k in keys:
        try:
            out = subprocess.run(["curl", "-s", "--max-time", "8",
                "-X", "POST", "https://api.capsolver.com/getBalance",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({"clientKey": k})],
                capture_output=True, text=True, timeout=12)
            d = json.loads(out.stdout)
            bal = d.get("balance", 0) or 0
            if bal > best_balance:
                best_balance = bal
                client_key = k
        except Exception:
            continue
    if client_key:
        print(f"  Capsolver key {client_key[:12]}... (balance ${best_balance})")
    else:
        print("  Tidak ada Capsolver key dengan saldo — skip")
        return None

    task = {
        "type": "ReCaptchaV2TaskProxyLess",
        "websiteURL": page_url,
        "websiteKey": sitekey,
    }
    try:
        data = json.dumps({"clientKey": client_key, "task": task}).encode()
        req = urllib.request.Request("https://api.capsolver.com/createTask", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode())
        if resp.get("status") != "ready" and resp.get("errorId") != 0:
            print("  Capsolver createTask error:", resp)
            return None
        task_id = resp.get("taskId")
        if not task_id:
            return None
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(5)
            data = json.dumps({"clientKey": client_key, "taskId": task_id}).encode()
            req = urllib.request.Request("https://api.capsolver.com/getTaskResult", data=data,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read().decode())
            if resp.get("status") == "ready":
                return resp["solution"]["gRecaptchaResponse"]
        print("  Capsolver timeout")
        return None
    except Exception as e:
        print("  Capsolver error:", e)
        return None


# ---------------------------------------------------------------- wallet
def new_solana_wallet():
    kp = Keypair()
    return str(kp.pubkey()), bytes(kp.secret())


def base58_encode(b: bytes) -> str:
    import base58 as b58
    return b58.b58encode(b).decode()


def sign_siwe_message(message: str, secret64: bytes) -> str:
    """Sign SIWE message dengan Solana ed25519 (32 byte pertama = seed)."""
    seed = secret64[:32]
    signing_key = nacl.signing.SigningKey(seed)
    sig = signing_key.sign(message.encode("utf-8")).signature
    return base58_encode(sig)


def build_siwe_message(address: str, nonce: str, issued_at: str, expiration: str) -> str:
    return (
        f"gmgn.ai wants you to sign in with your Solana account:\n{address}\n\n"
        f"wallet_sign_statement\n"
        f"URI: https://gmgn.ai\n"
        f"Version: 1\n"
        f"Chain ID: 900\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {issued_at}\n"
        f"Expiration Time: {expiration}"
    )


# ---------------------------------------------------------------- follow
def follow_target_wallets(access_token):
    """Follow semua wallet di FOLLOW_TARGETS. Return list hasil."""
    results = []
    for chain, addrs in FOLLOW_TARGETS.items():
        for addr in addrs:
            try:
                status, body = http_post(api_path("/api/v1/follow/follow_wallet"), {
                    "chain": chain,
                    "wallet_addresses": [addr],
                    "remark_addresses": [],
                }, headers={"Authorization": f"Bearer {access_token}"})
                ok = status == 200 and '"code":0' in body
                print(f"  Follow {chain}:{addr[:16]}... -> {'OK' if ok else 'GAGAL ' + str(status)}")
                results.append({"chain": chain, "address": addr, "ok": ok})
            except Exception as e:
                print(f"  Follow {addr[:16]}... error: {e}")
                results.append({"chain": chain, "address": addr, "ok": False})
    return results


# ---------------------------------------------------------------- main
def create_account():
    print("=" * 60)
    print("GMGN AUTO-CREATE")
    print("=" * 60)

    # 1. wallet baru
    pub, secret = new_solana_wallet()
    print(f"\n[1/5] Wallet Solana baru: {pub}")

    # 2. captcha halaman
    print("[2/5] Solve captcha halaman...")
    token_a = solve_recaptcha(SITEKEY_PAGE)
    if not token_a:
        print("GAGAL: captcha halaman")
        return None

    # 3. step 1: initiate
    print("[3/5] Initiate login...")
    step1_ts = time.time()
    status, body = http_post(api_path("/account/account/login_by_wallet"), {
        "address": pub,
        "wallet_type": "Phantom",
        "chain": "sol",
        "captcha_token": token_a,
    })
    if status != 200:
        print("GAGAL: step 1 status", status, body[:200])
        return None
    r1 = json.loads(body)
    if r1.get("code") != 0:
        print("GAGAL: step 1", r1)
        return None
    session_id = r1["data"]["session_id"]
    nonce = r1["data"].get("data", {}).get("nonce", "")
    print(f"  Session: {session_id} | nonce: {nonce}")

    # 4. captcha register + sign
    print("[4/5] Solve captcha register + sign message...")
    token_b = solve_recaptcha(SITEKEY_REGISTER, action="wallet_register")
    if not token_b:
        print("GAGAL: captcha register")
        return None

    issued = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(step1_ts))
    expiration = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(step1_ts + 300))
    message = build_siwe_message(pub, nonce, issued, expiration)
    signature = sign_siwe_message(message, secret)

    # 5. step 2: login
    print("[5/5] Login & buat akun...")
    status, body = http_post(api_path("/account/account/login_by_wallet"), {
        "session_id": session_id,
        "address": pub,
        "wallet_type": "Phantom",
        "chain": "sol",
        "captcha_token": token_b,
        "message": message,
        "signature": signature,
    })
    if status != 200:
        print("GAGAL: step 2 status", status, body[:200])
        return None
    r2 = json.loads(body)
    if r2.get("code") != 0:
        print("GAGAL: step 2", json.dumps(r2, ensure_ascii=False)[:300])
        return None

    tok = r2["data"]["data"]
    access_token = tok["access_token"]["token"]
    print(f"\n✅ AKUN BERHASIL DIBUAT: {pub}")
    print(f"   access_token: {access_token[:30]}...")

    # auto-follow
    print("\nAuto-follow wallet target...")
    follow_results = follow_target_wallets(access_token)

    return {
        "address": pub,
        "secret_b58": base58_encode(secret),
        "access_token": access_token,
        "refresh_token": tok["refresh_token"]["token"],
        "expire_at": tok["access_token"]["expire_at"],
        "followed": follow_results,
    }


def save_account(acc):
    os.makedirs(os.path.dirname(ACCOUNTS_PATH), exist_ok=True)
    existing = []
    if os.path.exists(ACCOUNTS_PATH):
        try:
            existing = json.load(open(ACCOUNTS_PATH))
        except Exception:
            existing = []
    existing.append(acc)
    with open(ACCOUNTS_PATH, "w") as fh:
        json.dump(existing, fh, indent=2)
    print(f"\n💾 Akun disimpan: {ACCOUNTS_PATH} (total {len(existing)} akun)")


if __name__ == "__main__":
    acc = create_account()
    if acc:
        save_account(acc)
    else:
        print("\n❌ Gagal membuat akun.")
        sys.exit(1)
