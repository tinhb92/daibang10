#!/usr/bin/env python3
"""
Robinhood Desk Telegram Alerter
Sends operational alerts (Gas spike breaches, toxic drifts, order fills)
Primary Bot: 8609659416:AAEBGuiFu3SjmVABHG-TSDwZzxOFxzr31EU (@pendleV2_bot)
Target Chat: 8478829054
"""

import os
import json
import urllib.request
import urllib.error

PRIMARY_BOT_TOKEN = "8609659416:AAEBGuiFu3SjmVABHG-TSDwZzxOFxzr31EU"
FALLBACK_BOT_TOKEN = "8921099549:AAHRefEbU_5Wc_cK-GDfaowr9garoK_8SNk"
DEFAULT_CHAT_ID = "8478829054"

def get_chat_id():
    # Try reading from .env if present
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

def send_telegram_alert(text: str, parse_mode: str = "HTML") -> bool:
    """
    Sends an alert to Telegram using @pendleV2_bot, falling back to secondary bot if needed.
    """
    chat_id = get_chat_id()
    
    # 1. Try primary bot (@pendleV2_bot)
    primary_url = f"https://api.telegram.org/bot{PRIMARY_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    
    try:
        req = urllib.request.Request(
            primary_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            if data.get("ok"):
                print("📱 Telegram alert sent via @pendleV2_bot")
                return True
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode()
        # If chat not started yet, use fallback bot so alert is not lost
        if "chat not found" in err_msg.lower():
            print("⚠️ @pendleV2_bot: Chat not started yet. Sending via shared fallback bot...")
            try:
                fallback_url = f"https://api.telegram.org/bot{FALLBACK_BOT_TOKEN}/sendMessage"
                f_req = urllib.request.Request(
                    fallback_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(f_req, timeout=8) as f_resp:
                    f_data = json.loads(f_resp.read().decode())
                    if f_data.get("ok"):
                        print("📱 Telegram alert delivered via fallback bot!")
                        return True
            except Exception as f_err:
                print(f"❌ Fallback alert error: {f_err}")
        else:
            print(f"❌ Telegram HTTP error: {e.code} - {err_msg}")
    except Exception as e:
        print(f"❌ Telegram send error: {e}")
        
    return False

if __name__ == "__main__":
    test_msg = (
        "🦅 <b>[Pendle V2 Robinhood Desk] Alerter Initialized</b>\n\n"
        "• <b>Network:</b> Robinhood Chain (4663)\n"
        "• <b>Gas Ceiling Guard:</b> 720,000 units (~$0.22 USD)\n"
        "• <b>Status:</b> Active"
    )
    send_telegram_alert(test_msg)
