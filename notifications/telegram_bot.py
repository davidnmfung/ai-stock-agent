import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)


class TelegramNotifier:

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def send_message(self, message: str) -> bool:
        """發送 Telegram Markdown 格式訊息"""
        if not self.bot_token or not self.chat_id:
            print("[Telegram 警告] 未設定 Token 或 Chat ID，無法發送訊息。")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }

        try:
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                return True
            else:
                print(
                    f"[Telegram 錯誤] 發送失敗 ({res.status_code}): {res.text}"
                )
                return False
        except Exception as e:
            print(f"[Telegram 異常] 連線失敗: {e}")
            return False