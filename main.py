import os
import time
import requests
import pandas as pd
import json

# ---------------------------------------------------------------------------
# Telegram 推播設定 (請確認填入你的 Bot Token 與 Chat ID，或從環境變數讀取)
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")


def send_telegram_summary(message: str):
    """發送單一彙整式 Telegram 訊息"""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("⚠️ 未設定 TELEGRAM_BOT_TOKEN，僅在主控台輸出：\n", message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print("✅ 彙整預警訊息已成功推播至 Telegram！")
        else:
            print(f"❌ Telegram 推播失敗: {res.text}")
    except Exception as e:
        print(f"⚠️ Telegram API 發送異常: {e}")


class RealtimeAgentScanner:
    def __init__(self):
        # 擴充版 Small-Cap 標的池 (25+ 檔高波動熱門飆股)
        self.watchlist = [
            "SMCX", "AIOT", "SOUN", "BBAI", "RGTI", "QUBT", "CRML", "GRML", "GLND",
            "IONQ", "PLTR", "MARA", "RIOT", "CLSK", "SOFI", "UPST", "AFRM", "PATH", 
            "ASTS", "RKLB", "JOBY", "LUNR", "OKLO", "SMR", "NBIS"
        ]
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def fetch_realtime_data(self, ticker: str) -> pd.DataFrame:
        """獲取最新 30 天日 K 數據"""
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1m&interval=1d"
        try:
            res = self.session.get(url, timeout=10)
            if res.status_code != 200:
                return pd.DataFrame()

            chart = res.json().get("chart", {}).get("result", [{}])[0]
            timestamps = chart.get("timestamp", [])
            indicators = chart.get("indicators", {}).get("quote", [{}])[0]

            if not timestamps or not indicators:
                return pd.DataFrame()

            df = pd.DataFrame({
                "timestamp": pd.to_datetime(timestamps, unit="s"),
                "open": indicators.get("open", []),
                "high": indicators.get("high", []),
                "low": indicators.get("low", []),
                "close": indicators.get("close", []),
                "volume": indicators.get("volume", [])
            }).dropna()

            return df
        except Exception:
            return pd.DataFrame()

    def scan_market(self):
        print(f"\n🔍 執行 AI Stock Agent 市場掃描...")
        print(f"📋 載入觀察清單 ({len(self.watchlist)} 檔): {self.watchlist}")

        triggered_alerts = []

        for ticker in self.watchlist:
            df = self.fetch_realtime_data(ticker)
            if df.empty or len(df) < 20:
                continue

            # 計算指標
            df["vol_ma5"] = df["volume"].rolling(window=5).mean().shift(1)
            df["rvol"] = df["volume"] / df["vol_ma5"]
            df["ma20"] = df["close"].rolling(window=20).mean()
            df["day_change"] = (df["close"] - df["open"]) / df["open"]

            latest = df.iloc[-1]
            price = round(latest["close"], 2)
            rvol = round(latest["rvol"], 2) if pd.notnull(latest["rvol"]) else 0.0
            day_pct = round(latest["day_change"] * 100, 2)
            ma20 = latest["ma20"]

            # 技術面突破門檻
            cond_rvol = rvol >= 2.0
            cond_bull = latest["day_change"] >= 0.03
            cond_trend = price > ma20 if pd.notnull(ma20) else True
            cond_not_overextended = ((price - ma20) / ma20) <= 0.15 if pd.notnull(ma20) and ma20 > 0 else True

            if cond_rvol and cond_bull and cond_trend and cond_not_overextended:
                # 收集觸發預警的股票資訊
                alert_text = (
                    f"• *${ticker}* | 價格: `${price}` | 漲幅: `+{day_pct}%` | RVOL: `{rvol}x`\n"
                    f"  💡 _突破 MA20 均線，量能放大 {rvol} 倍，符合起漲訊號。_"
                )
                triggered_alerts.append(alert_text)
                print(f"🎯 [觸發預警] ${ticker} - 價格: ${price}, RVOL: {rvol}x, 漲幅: +{day_pct}%")

            time.sleep(0.05)

        # 彙整發送單一 Telegram 報告
        if triggered_alerts:
            summary_message = (
                f"🚀 *AI 爆發股市場監控預警 (單一彙整報告)*\n\n"
                f"當前共有 *{len(triggered_alerts)}* 檔標的符合爆量突破條件：\n\n"
                + "\n\n".join(triggered_alerts)
                + f"\n\n⏰ 掃描時間: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_telegram_summary(summary_message)
        else:
            print("ℹ️ 本輪掃描無符合條件之爆發股，暫不推播訊息。")


if __name__ == "__main__":
    print("🤖 AI Stock Agent 已啟動，開始於美股盤中常駐監控 (每 5 分鐘自動掃描一次) ...")
    scanner = RealtimeAgentScanner()
    
    while True:
        try:
            scanner.scan_market()
            print("\n⏳ 等待 5 分鐘後進行下一次市場掃描... (可按 Ctrl + C 停止運行)")
            time.sleep(300)
        except KeyboardInterrupt:
            print("\n🛑 手動停止監控程序。")
            break
        except Exception as e:
            print(f"⚠️ 運行中發生錯誤: {e}")
            time.sleep(60)