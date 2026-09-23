import os
import time
import requests
import pandas as pd
import json

# ---------------------------------------------------------------------------
# Telegram 推播設定 (固定預設憑證，亦可由環境變數覆蓋)
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8894423509:AAF-pYhPtoW1kQeR8rLf0TwtcIw1tlCVLwA")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "852353260")


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
        # 核心 Small-Cap 固定觀察清單 (25 檔熱門股)
        self.core_watchlist = [
            "SMCX", "AIOT", "SOUN", "BBAI", "RGTI", "QUBT", "CRML", "GRML", "GLND",
            "IONQ", "PLTR", "MARA", "RIOT", "CLSK", "SOFI", "UPST", "AFRM", "PATH", 
            "ASTS", "RKLB", "JOBY", "LUNR", "OKLO", "SMR", "NBIS"
        ]
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def fetch_dynamic_top_gainers(self) -> list:
        """動態抓取美股當日市場漲幅/爆量前 25 名的飆股標的"""
        url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds=day_gainers&count=25"
        try:
            res = self.session.get(url, timeout=10)
            if res.status_code == 200:
                results = res.json().get("finance", {}).get("result", [{}])[0].get("quotes", [])
                # 篩選價格 <= $50 的 Small/Mid-Cap 標的，避開權值股與指數 ETF
                dynamic_tickers = [
                    q["symbol"] for q in results 
                    if "symbol" in q 
                    and "^" not in q["symbol"] 
                    and "." not in q["symbol"] 
                    and q.get("regularMarketPrice", 999) <= 50
                ]
                print(f"🔥 [動態熱門飆股篩選] 今日實時市場獲取 {len(dynamic_tickers)} 檔大漲標的: {dynamic_tickers}")
                return dynamic_tickers
        except Exception as e:
            print(f"⚠️ 動態飆股抓取失敗 (將維持使用核心清單): {e}")
        return []

    def get_full_watchlist(self) -> list:
        """合併固定觀察清單與每日動態熱門飆股（自動去重）"""
        dynamic_tickers = self.fetch_dynamic_top_gainers()
        # dict.fromkeys 可確保去重的同時保留清單順序
        combined = list(dict.fromkeys(self.core_watchlist + dynamic_tickers))
        return combined

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
        watchlist = self.get_full_watchlist()
        print(f"\n🔍 執行 AI Stock Agent 市場掃描...")
        print(f"📋 載入總監控清單 (共 {len(watchlist)} 檔): {watchlist}")

        triggered_alerts = []

        for ticker in watchlist:
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

            # 技術面突破門檻 (RVOL >= 2.0, 漲幅 >= 3%, 站上 MA20 且離 MA20 不超過 15%)
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
                f"🚀 *AI 爆發股市場監控預警 (動態彙整報告)*\n\n"
                f"當前共有 *{len(triggered_alerts)}* 檔標的符合爆量突破條件：\n\n"
                + "\n\n".join(triggered_alerts)
                + f"\n\n⏰ 掃描時間: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_telegram_summary(summary_message)
        else:
            print("ℹ️ 本輪掃描無符合條件之爆發股，暫不推播訊息。")


if __name__ == "__main__":
    print("🤖 AI Stock Agent 已啟動，開始於美股盤中常駐監控 (含動態熱門飆股篩選) ...")
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