import os
import pandas as pd
from datetime import datetime

HISTORY_FILE = "data/signal_history.csv"

class SignalTracker:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self._ensure_file()

    def _ensure_file(self):
        """確保 CSV 檔案存在且包含正確的欄位"""
        expected_columns = ["date", "ticker", "price", "gain_pct", "rvol", "ai_score", "catalyst"]
        if not os.path.exists(HISTORY_FILE) or os.path.getsize(HISTORY_FILE) == 0:
            df = pd.DataFrame(columns=expected_columns)
            df.to_csv(HISTORY_FILE, index=False)
        else:
            try:
                df = pd.read_csv(HISTORY_FILE)
                if not all(col in df.columns for col in expected_columns):
                    # 欄位不符則重建
                    df = pd.DataFrame(columns=expected_columns)
                    df.to_csv(HISTORY_FILE, index=False)
            except Exception:
                df = pd.DataFrame(columns=expected_columns)
                df.to_csv(HISTORY_FILE, index=False)

    def log_signal(self, ticker, price, gain_pct, rvol, ai_score, catalyst):
        """記錄新的飆股信號"""
        self._ensure_file()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        try:
            df = pd.read_csv(HISTORY_FILE)
        except Exception:
            df = pd.DataFrame(columns=["date", "ticker", "price", "gain_pct", "rvol", "ai_score", "catalyst"])
        
        # 避免同一天重複記錄相同代號
        if df.empty or not "date" in df.columns or not ((df["date"] == today_str) & (df["ticker"] == ticker)).any():
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
        try:
            df = pd.read_csv(HISTORY_FILE)
            if df.empty or "ai_score" not in df.columns:
                return "尚無歷史信號記錄。"
            
            total_signals = len(df)
            avg_score = df["ai_score"].mean()
            return f"📊 歷史累計信號數: {total_signals} 筆 | 平均 AI 評分: {round(avg_score, 1)}/10"
        except Exception:
            return "尚無歷史信號記錄。"