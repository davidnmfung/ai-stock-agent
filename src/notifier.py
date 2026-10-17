import requests
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(message: str) -> bool:
    """發送長訊息至 Telegram 群組（自動分段處理）"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ 錯誤: 缺少 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID。")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    MAX_CHAR = 3500
    chunks = [message[i : i + MAX_CHAR] for i in range(0, len(message), MAX_CHAR)]

    success = True
    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        try:
            res = requests.post(url, json=payload, timeout=10)
            res.raise_for_status()
        except Exception as e:
            print(f"❌ Telegram 發送失敗: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"   響應內容: {e.response.text}")
            success = False

    return success