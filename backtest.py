import os
import time
import requests
import pandas as pd
import json


class BacktestEngine:
    def __init__(self, tickers=None):
        self.tickers = tickers or ["SMCX", "AIOT", "SOUN", "BBAI", "RGTI", "QUBT", "CRML", "GRML", "GLND"]
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def fetch_history(self, ticker: str, period: str = "30d", interval: str = "1d") -> pd.DataFrame:
        """從 Yahoo v8 API 獲取歷史 OHLCV 數據"""
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={period}&interval={interval}"
        try:
            res = self.session.get(url, timeout=10)
            if res.status_code != 200:
                print(f"[{ticker}] 歷史數據獲取失敗 (HTTP {res.status_code})")
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

        except Exception as e:
            print(f"[{ticker}] 抓取異常: {e}")
            return pd.DataFrame()

    def run_backtest(self, ticker: str, rvol_thresh: float = 1.2, tp_pct: float = 0.10, sl_pct: float = 0.03):
        """
        執行單一標的歷史回測
        - 買入觸發: RVOL > rvol_thresh (基於 5 日均量)
        - 停利點 (TP): +10%
        - 停損點 (SL): -3%
        """
        df = self.fetch_history(ticker, period="60d", interval="1d")
        if df.empty or len(df) < 10:
            print(f"⚠️ [{ticker}] 歷史數據不足，跳過回測。")
            return None

        # 計算 5 日平均成交量與 RVOL
        df["vol_ma5"] = df["volume"].rolling(window=5).mean().shift(1)
        df["rvol"] = df["volume"] / df["vol_ma5"]

        trades = []
        
        for i in range(5, len(df) - 1):
            row = df.iloc[i]
            
            # 觸發買入條件
            if row["rvol"] >= rvol_thresh:
                entry_price = row["close"]
                entry_date = row["timestamp"]
                tp_price = entry_price * (1 + tp_pct)
                sl_price = entry_price * (1 - sl_pct)

                trade_result = None
                exit_price = entry_price
                exit_date = None

                # 模擬未來最多 5 個交易日的走勢
                for j in range(i + 1, min(i + 6, len(df))):
                    future_row = df.iloc[j]
                    
                    # 先看是否觸及停損，再看是否觸及停利
                    if future_row["low"] <= sl_price:
                        trade_result = "LOSS"
                        exit_price = sl_price
                        exit_date = future_row["timestamp"]
                        break
                    elif future_row["high"] >= tp_price:
                        trade_result = "WIN"
                        exit_price = tp_price
                        exit_date = future_row["timestamp"]
                        break

                # 若 5 天內未平倉，強行以第 5 天收盤價平倉
                if not trade_result:
                    exit_row = df.iloc[min(i + 5, len(df) - 1)]
                    exit_price = exit_row["close"]
                    exit_date = exit_row["timestamp"]
                    trade_result = "WIN" if exit_price > entry_price else "LOSS"

                pnl_pct = (exit_price - entry_price) / entry_price
                trades.append({
                    "ticker": ticker,
                    "entry_date": entry_date.strftime("%Y-%m-%d"),
                    "entry_price": round(entry_price, 2),
                    "exit_date": exit_date.strftime("%Y-%m-%d") if exit_date else "N/A",
                    "exit_price": round(exit_price, 2),
                    "result": trade_result,
                    "pnl_pct": round(pnl_pct * 100, 2)
                })

        return trades

    def evaluate_all(self):
        print("📊 開始執行 AI Stock Agent 歷史勝率與期望值回測...\n" + "="*50)
        all_trades = []

        for ticker in self.tickers:
            trades = self.run_backtest(ticker)
            if trades:
                all_trades.extend(trades)
            time.sleep(0.2)

        if not all_trades:
            print("❌ 無法取得足夠交易記錄進行統計。")
            return

        tdf = pd.DataFrame(all_trades)
        total_trades = len(tdf)
        wins = len(tdf[tdf["result"] == "WIN"])
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        avg_pnl = tdf["pnl_pct"].mean()

        print(f"📈 【回測總結報告】")
        print(f"• 標的數量: {len(self.tickers)} 檔")
        print(f"• 總觸發交易次數: {total_trades} 次")
        print(f"• 總勝率: {win_rate:.2f}% ({wins}/{total_trades})")
        print(f"• 平均單次收益率: {avg_pnl:+.2f}%")
        print("="*50)
        print("\n📋 詳細交易記錄範例:")
        print(tdf.tail(10).to_string(index=False))


if __name__ == "__main__":
    # 載入 watchlist.json 配置
    watchlist_path = os.path.join("config", "watchlist.json")
    tickers = None
    if os.path.exists(watchlist_path):
        with open(watchlist_path, "r", encoding="utf-8") as f:
            tickers = json.load(f).get("watchlist", [])

    engine = BacktestEngine(tickers=tickers)
    engine.evaluate_all()