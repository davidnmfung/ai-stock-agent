import os
import time
import requests
import pandas as pd
import json


class BacktestEngine:
    def __init__(self, mode: str = "sp500"):
        """
        mode 模式選項:
        - 'sp500': 測試 S&P 500 500檔成分股
        - 'smallcap': 測試熱門 Small-Cap 中小型高波動股
        - 'custom': 載入 config/watchlist.json 自訂清單
        """
        self.mode = mode
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.tickers = self._load_tickers()

    def _load_tickers(self) -> list:
        if self.mode == "sp500":
            print("🌐 正在自動擷取 S&P 500 最新成分股清單...")
            try:
                url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
                tables = pd.read_html(url)
                tickers = tables[0]['Symbol'].str.replace('.', '-', regex=False).tolist()
                print(f"✅ 成功載入 {len(tickers)} 檔 S&P 500 成分股。")
                return tickers
            except Exception as e:
                print(f"⚠️ 無法取得 S&P 500 清單 ({e})，改用預設大型股。")
                return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD"]

        elif self.mode == "smallcap":
            # Russell 2000 / 熱門 Small-Cap 高波動標的池
            print("⚡ 載入 Small-Cap 中小型高波動股觀察清單...")
            return [
                "SMCX", "AIOT", "SOUN", "BBAI", "RGTI", "QUBT", "CRML", "GRML", "GLND",
                "IONQ", "PLTR", "MARA", "RIOT", "CLSK", "SOFI", "UPST", "AFRM", "PATH", 
                "ASTS", "RKLB", "JOBY", "LUNR", "OKLO", "SMR", "NBIS"
            ]

        else:
            # 載入 config/watchlist.json
            watchlist_path = os.path.join("config", "watchlist.json")
            if os.path.exists(watchlist_path):
                with open(watchlist_path, "r", encoding="utf-8") as f:
                    tickers = json.load(f).get("watchlist", [])
                    print(f"📂 從 config/watchlist.json 載入 {len(tickers)} 檔標的。")
                    return tickers
            return ["SMCX", "SOUN", "BBAI", "NVDA"]

    def fetch_history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """從 Yahoo v8 API 獲取長週期歷史數據 (預設 1y = 1 年)"""
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={period}&interval={interval}"
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

    def run_backtest(self, ticker: str, period: str = "1y", rvol_thresh: float = 2.0, tp_pct: float = 0.10, sl_pct: float = 0.03):
        """
        長週期歷史回測引擎
        - 買入觸發: RVOL >= 2.0 + 當日漲幅 >= 3% + 站上 MA20 均線
        - 風控出場: 停利 +10%, 停損 -3%, 最長持倉 5 天
        """
        df = self.fetch_history(ticker, period=period, interval="1d")
        if df.empty or len(df) < 20:
            return None

        df["vol_ma5"] = df["volume"].rolling(window=5).mean().shift(1)
        df["rvol"] = df["volume"] / df["vol_ma5"]
        df["ma20"] = df["close"].rolling(window=20).mean()
        df["day_change"] = (df["close"] - df["open"]) / df["open"]

        trades = []
        
        for i in range(20, len(df) - 1):
            row = df.iloc[i]
            
            cond_rvol = row["rvol"] >= rvol_thresh
            cond_bull = row["day_change"] >= 0.03
            cond_trend = row["close"] > row["ma20"] if pd.notnull(row["ma20"]) else True

            if cond_rvol and cond_bull and cond_trend:
                entry_price = row["close"]
                entry_date = row["timestamp"]
                tp_price = entry_price * (1 + tp_pct)
                sl_price = entry_price * (1 - sl_pct)

                trade_result = None
                exit_price = entry_price
                exit_date = None

                for j in range(i + 1, min(i + 6, len(df))):
                    future_row = df.iloc[j]
                    
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

    def evaluate_all(self, period: str = "1y"):
        print(f"\n📊 開始執行 AI Stock Agent 大數據壓力測試...")
        print(f"• 標的池模式: {self.mode.upper()}")
        print(f"• 回測時間跨度: {period} (歷史天數)")
        print("="*60)

        all_trades = []
        processed_count = 0

        for ticker in self.tickers:
            trades = self.run_backtest(ticker, period=period)
            if trades:
                all_trades.extend(trades)
            
            processed_count += 1
            if processed_count % 50 == 0 or processed_count == len(self.tickers):
                print(f"⏳ 進度: [{processed_count}/{len(self.tickers)}] 已完成掃描...")

            time.sleep(0.05)  # 防封包冷卻

        if not all_trades:
            print("❌ 無符合條件之交易訊號或歷史數據不足。")
            return

        tdf = pd.DataFrame(all_trades)
        total_trades = len(tdf)
        wins = len(tdf[tdf["result"] == "WIN"])
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        avg_pnl = tdf["pnl_pct"].mean()

        print("\n" + "="*60)
        print(f"📈 【長週期壓力測試總結報告】")
        print(f"• 掃描總標的數: {len(self.tickers)} 檔")
        print(f"• 總觸發交易次數: {total_trades} 次")
        print(f"• 總勝率: {win_rate:.2f}% ({wins}/{total_trades})")
        print(f"• 平均單次收益率: {avg_pnl:+.2f}%")
        print("="*60)
        print("\n📋 近期交易記錄範例:")
        print(tdf.tail(15).to_string(index=False))


if __name__ == "__main__":
    # 預設執行 Small-Cap 測試 (若要跑 S&P 500 請傳入 mode="sp500")
    # 可調整時間跨度 period="1y" (1年) 或 "2y" (2年)
    engine = BacktestEngine(mode="smallcap")
    engine.evaluate_all(period="1y")