import os
import pandas as pd
from datetime import datetime

HISTORY_FILE = "data/signal_history.csv"

class SignalTracker:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(HISTORY_FILE):
            df = pd.DataFrame(columns=[
                "date", "ticker", "price", "gain_pct", "rvol", "ai_score", "catalyst"
            ])
            df.to_csv(HISTORY_FILE, index=False)

    def log_signal(self, ticker, price, gain_pct, rvol, ai_score, catalyst):
        """記錄新的飆股信號"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        df = pd.read_csv(HISTORY_FILE)
        
        # 避免同一天重複記錄相同代號
        if not ((df["date"] == today_str) & (df["ticker"] == ticker)).any():
            new_row = pd.DataFrame([{
                "date": today_str,
                "ticker": ticker,
                "price": price,
                "gain_pct": gain_pct,
                "rvol": rvol,
                "ai_score": ai_score,
                "catalyst": catalyst
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(HISTORY_FILE, index=False)
            print(f"📝 [SignalTracker] 已記錄信號: ${ticker} (AI 評分: {ai_score})")

    def get_history_summary(self):
        """讀取歷史信號統計摘要"""
        if not os.path.exists(HISTORY_FILE):
            return "尚無歷史信號記錄。"
        df = pd.read_csv(HISTORY_FILE)
        if df.empty:
            return "尚無歷史信號記錄。"
        
        total_signals = len(df)
        avg_score = df["ai_score"].mean() if "ai_score" in df.columns else 0.0
        return f"📊 歷史累計信號數: {total_signals} 筆 | 平均 AI 評分: {round(avg_score, 1)}/10"