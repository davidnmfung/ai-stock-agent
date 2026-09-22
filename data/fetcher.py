import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import yfinance as yf


class StockFetcher:

    def __init__(self, tickers=None):
        # 預設關注清單，亦可於初始化時動態傳入
        self.tickers = tickers or [
            "SMCX",
            "AIOT",
            "SOUN",
            "BBAI",
            "RGTI",
            "QUBT",
        ]
        self.session = self._create_session()

    def _create_session(self):
        """建立帶有自動重試機制與完整 Header 的 Requests Session，防範 PythonAnywhere HTTP 429 封鎖"""
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
        })

        # 設定 HTTP 429 與 5xx 錯誤時自動重試機制
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def get_top_gainers_or_surges(self, custom_tickers=None):
        targets = custom_tickers or self.tickers
        results = []

        for ticker_symbol in targets:
            try:
                ticker = yf.Ticker(ticker_symbol, session=self.session)
                df = ticker.history(period="5d")

                if df.empty or len(df) < 2:
                    print(
                        f"[{ticker_symbol}] 數據無效或回傳空白 (可能是 HTTP"
                        " 429)，跳過。"
                    )
                    continue

                latest = df.iloc[-1]
                price = round(float(latest["Close"]), 2)

                avg_volume = df["Volume"].mean()
                latest_volume = float(latest["Volume"])
                rvol = (
                    round(float(latest_volume / avg_volume), 2)
                    if avg_volume > 0
                    else 1.0
                )

                # 🌟 改用 fast_info 獲取市值，避免呼叫 ticker.info 觸發 Crumb 429 封鎖
                market_cap = 0
                try:
                    fast_info = getattr(ticker, "fast_info", {})
                    market_cap = fast_info.get("market_cap", 0) or 0
                except Exception:
                    market_cap = 0

                results.append({
                    "ticker": ticker_symbol,
                    "price": price,
                    "rvol": rvol,
                    "market_cap": market_cap,
                })

                # 每次請求間隔 0.5 秒，避免頻繁請求觸發風控
                time.sleep(0.5)

            except Exception as e:
                print(f"[{ticker_symbol} 擷取失敗]: {e}")

        return results