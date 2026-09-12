#!/usr/bin/env python3
"""
Robinhood Desk Telegram Alerter
Sends operational alerts (Gas spike breaches, toxic drifts, order fills, heartbeats)
Primary Bot: 8609659416:AAEBGuiFu3SjmVABHG-TSDwZzxOFxzr31EU (@pendleV2_bot)
Target Chat: 8478829054
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error

PRIMARY_BOT_TOKEN = "8609659416:AAEBGuiFu3SjmVABHG-TSDwZzxOFxzr31EU"
FALLBACK_BOT_TOKEN = "8921099549:AAHRefEbU_5Wc_cK-GDfaowr9garoK_8SNk"
DEFAULT_CHAT_ID = "8478829054"

_LAST_ALERT_TIME = 0.0
TELEGRAM_MIN_GAP = 1.2  # Minimum seconds between Telegram API calls to prevent 429

def get_chat_id():
    search_paths = [
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        "/Users/tin/eagle/daibang9/.env"
    ]
    for p in search_paths:
        if os.path.exists(p):
            try:
                with open(p) as f:
                    for line in f:
                        if "TELEGRAM_CHAT_ID" in line and "=" in line:
                            val = line.split("=", 1)[1].strip().strip("\"'")
                            if val:
                                return val
            except Exception:
                pass
    return DEFAULT_CHAT_ID

def send_telegram_alert(text: str, parse_mode: str = "HTML", max_retries: int = 3, disable_notification: bool = False) -> bool:
    """
    Sends an alert to Telegram with rate-limiting gap and fallback bot support.
    """
    global _LAST_ALERT_TIME
    chat_id = get_chat_id()

    # Enforce rate-limit interval
    elapsed = time.time() - _LAST_ALERT_TIME
    if elapsed < TELEGRAM_MIN_GAP:
        time.sleep(TELEGRAM_MIN_GAP - elapsed)

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
        "disable_notification": disable_notification
    }

    for attempt in range(1, max_retries + 1):
        try:
            primary_url = f"https://api.telegram.org/bot{PRIMARY_BOT_TOKEN}/sendMessage"
            req = urllib.request.Request(
                primary_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if data.get("ok"):
                    _LAST_ALERT_TIME = time.time()
                    print("📱 Telegram alert delivered via @pendleV2_bot")
                    return True
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode()
            if e.code == 429:
                retry_after = 3.0
                try:
                    data = json.loads(err_msg)
                    retry_after = float(data.get("parameters", {}).get("retry_after", 3.0)) + 0.5
                except Exception:
                    pass
                print(f"⏳ Telegram rate limit (429) hit, waiting {retry_after:.1f}s (attempt {attempt}/{max_retries})...")
                time.sleep(retry_after)
                continue
            elif "chat not found" in err_msg.lower():
                print("⚠️ @pendleV2_bot chat not started. Trying fallback bot...")
                try:
                    fallback_url = f"https://api.telegram.org/bot{FALLBACK_BOT_TOKEN}/sendMessage"
                    f_req = urllib.request.Request(
                        fallback_url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(f_req, timeout=10) as f_resp:
                        f_data = json.loads(f_resp.read().decode())
                        if f_data.get("ok"):
                            _LAST_ALERT_TIME = time.time()
                            print("📱 Telegram alert delivered via fallback bot!")
                            return True
                except Exception as f_err:
                    print(f"❌ Fallback alert failed: {f_err}")
                    break
            elif e.code == 400 and ("parse entities" in err_msg.lower() or "bad request" in err_msg.lower()):
                import re
                try:
                    clean_text = re.sub(r"<[^>]+>", "", text)
                    fb_payload = dict(payload, text=clean_text, parse_mode=None)
                    req_fb = urllib.request.Request(
                        primary_url,
                        data=json.dumps(fb_payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req_fb, timeout=10) as resp_fb:
                        data_fb = json.loads(resp_fb.read().decode())
                        if data_fb.get("ok"):
                            _LAST_ALERT_TIME = time.time()
                            print("📱 Telegram alert delivered via @pendleV2_bot (plain-text fallback)")
                            return True
                except Exception:
                    pass
                print(f"❌ Telegram HTTP error {e.code}: {err_msg}")
            else:
                print(f"❌ Telegram HTTP error {e.code}: {err_msg}")
                time.sleep(1.0 * attempt)
        except Exception as e:
            print(f"❌ Telegram send error (attempt {attempt}/{max_retries}): {e}")
            time.sleep(1.0 * attempt)

    return False

if __name__ == "__main__":
    test_msg = (
        "🦅 <b>[PENDLE V2 DESK • ALERTER TEST]</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• <b>Network:</b> Robinhood Chain (4663)\n"
        "• <b>Status:</b> Nominal & Rate-Limited\n"
        "• <b>Time:</b> Verified"
    )
    send_telegram_alert(test_msg)
