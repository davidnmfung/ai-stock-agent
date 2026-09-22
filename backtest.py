import os
import time
import requests
import pandas as pd
import json


class BacktestEngine:
    def __init__(self, mode: str = "smallcap"):
        """
        mode 模式選項:
        - 'smallcap': 測試熱門 Small-Cap 中小型高波動股 (預設)
        - 'sp500': 測試 S&P 500 成分股
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
            print("⚡ 載入 Small-Cap 中小型高波動股觀察清單...")
            return [
                "SMCX", "AIOT", "SOUN", "BBAI", "RGTI", "QUBT", "CRML", "GRML", "GLND",
                "IONQ", "PLTR", "MARA", "RIOT", "CLSK", "SOFI", "UPST", "AFRM", "PATH", 
                "ASTS", "RKLB", "JOBY", "LUNR", "OKLO", "SMR", "NBIS"
            ]

        else:
            watchlist_path = os.path.join("config", "watchlist.json")
            if os.path.exists(watchlist_path):
                with open(watchlist_path, "r", encoding="utf-8") as f:
                    tickers = json.load(f).get("watchlist", [])
                    print(f"📂 從 config/watchlist.json 載入 {len(tickers)} 檔標的。")
                    return tickers
            return ["SMCX", "SOUN", "BBAI", "NVDA"]

    def fetch_history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """從 Yahoo v8 API 獲取長週期歷史數據"""
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

    def run_backtest(
        self, 
        ticker: str, 
        period: str = "1y", 
        rvol_thresh: float = 2.0, 
        tp_pct: float = 0.10, 
        sl_pct: float = 0.03,
        cooldown_days: int = 5,
        max_ma20_dist: float = 0.15
    ):
        """
        優化版長週期歷史回測引擎:
        1. 進場條件: RVOL >= 2.0 + 當日漲幅 >= 3% + 站上 MA20
        2. 偏離度過濾: (Close - MA20) / MA20 <= 15% (避免追高)
        3. 風控出場: 停利 +10%, 停損 -3%, 最長持倉 5 天
        4. 冷卻期機制: 停損後冷卻 5 個交易日禁止再次進場
        """
        df = self.fetch_history(ticker, period=period, interval="1d")
        if df.empty or len(df) < 20:
            return None

        df["vol_ma5"] = df["volume"].rolling(window=5).mean().shift(1)
        df["rvol"] = df["volume"] / df["vol_ma5"]
        df["ma20"] = df["close"].rolling(window=20).mean()
        df["day_change"] = (df["close"] - df["open"]) / df["open"]

        trades = []
        cooldown_until_idx = 0
        
        i = 20
        while i < len(df) - 1:
            # 若處於虧損冷卻期，跳過該交易日
            if i < cooldown_until_idx:
                i += 1
                continue

            row = df.iloc[i]
            
            cond_rvol = row["rvol"] >= rvol_thresh
            cond_bull = row["day_change"] >= 0.03
            
            # MA20 趨勢與偏離度檢查
            ma20 = row["ma20"]
            if pd.notnull(ma20) and ma20 > 0:
                cond_trend = row["close"] > ma20
                # 均線偏離度過濾：股價高出 MA20 不得超過 15%
                cond_not_overextended = ((row["close"] - ma20) / ma20) <= max_ma20_dist
            else:
                cond_trend = True
                cond_not_overextended = True

            if cond_rvol and cond_bull and cond_trend and cond_not_overextended:
                entry_price = row["close"]
                entry_date = row["timestamp"]
                tp_price = entry_price * (1 + tp_pct)
                sl_price = entry_price * (1 - sl_pct)

                trade_result = None
                exit_price = entry_price
                exit_date = None
                exit_idx = i

                # 模擬未來的持倉走勢 (最多 5 個交易日)
                for j in range(i + 1, min(i + 6, len(df))):
                    future_row = df.iloc[j]
                    
                    if future_row["low"] <= sl_price:
                        trade_result = "LOSS"
                        exit_price = sl_price
                        exit_date = future_row["timestamp"]
                        exit_idx = j
                        break
                    elif future_row["high"] >= tp_price:
                        trade_result = "WIN"
                        exit_price = tp_price
                        exit_date = future_row["timestamp"]
                        exit_idx = j
                        break

                # 持倉期滿平倉
                if not trade_result:
                    exit_idx = min(i + 5, len(df) - 1)
                    exit_row = df.iloc[exit_idx]
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

                # 若本次交易觸發 LOSS，設定 5 天冷卻期
                if trade_result == "LOSS":
                    cooldown_until_idx = exit_idx + cooldown_days + 1
                
                # 持倉期間不重複開倉，將指針推至平倉日後
                i = exit_idx + 1
            else:
                i += 1

        return trades

    def evaluate_all(self, period: str = "1y"):
        print(f"\n📊 開始執行 AI Stock Agent 大數據壓力測試 (冷卻期 + 均線偏離過濾)...")
        print(f"• 標的池模式: {self.mode.upper()}")
        print(f"• 回測時間跨度: {period}")
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

            time.sleep(0.05)

        if not all_trades:
            print("❌ 無符合條件之交易訊號或歷史數據不足。")
            return

        tdf = pd.DataFrame(all_trades)
        total_trades = len(tdf)
        wins = len(tdf[tdf["result"] == "WIN"])
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        avg_pnl = tdf["pnl_pct"].mean()

        print("\n" + "="*60)
        print(f"📈 【進階風控壓力測試總結報告】")
        print(f"• 掃描總標的數: {len(self.tickers)} 檔")
        print(f"• 總觸發交易次數: {total_trades} 次")
        print(f"• 總勝率: {win_rate:.2f}% ({wins}/{total_trades})")
        print(f"• 平均單次收益率: {avg_pnl:+.2f}%")
        print("="*60)
        print("\n📋 近期交易記錄範例:")
        print(tdf.tail(15).to_string(index=False))


if __name__ == "__main__":
    engine = BacktestEngine(mode="smallcap")
    engine.evaluate_all(period="1y")