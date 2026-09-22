import time
import requests


class StockFetcher:

    def __init__(self, tickers=None):
        self.tickers = tickers or [
            "SMCX",
            "AIOT",
            "SOUN",
            "BBAI",
            "RGTI",
            "QUBT",
        ]
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        })

    def get_top_gainers_or_surges(self, custom_tickers=None):
        targets = custom_tickers or self.tickers
        results = []

        for ticker in targets:
            try:
                # 呼叫不需要 Crumb / Cookie 的原生地圖 API
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1d"
                res = self.session.get(url, timeout=10)

                if res.status_code != 200:
                    print(
                        f"[{ticker}] HTTP Error {res.status_code}，跳過。"
                    )
                    continue

                data = res.json()
                chart_result = data.get("chart", {}).get("result")

                if not chart_result:
                    print(f"[{ticker}] 無數據，跳過。")
                    continue

                meta = chart_result[0].get("meta", {})
                price = round(
                    float(
                        meta.get("regularMarketPrice")
                        or meta.get("chartPreviousClose")
                        or 0
                    ),
                    2,
                )

                # 計算簡化 RVOL (當日成交量 vs 5日平均成交量)
                indicators = (
                    chart_result[0]
                    .get("indicators", {})
                    .get("quote", [{}])[0]
                )
                volumes = [
                    v for v in indicators.get("volume", []) if v is not None
                ]

                latest_vol = volumes[-1] if volumes else 0
                avg_vol = (
                    sum(volumes) / len(volumes) if len(volumes) > 0 else 1
                )
                rvol = (
                    round(latest_vol / avg_vol, 2) if avg_vol > 0 else 1.0
                )

                # 讀取市值
                market_cap = meta.get("marketCap", 0) or 0

                if price > 0:
                    results.append({
                        "ticker": ticker,
                        "price": price,
                        "rvol": rvol,
                        "market_cap": market_cap,
                    })

                time.sleep(0.3)  # 請求間隔保護

            except Exception as e:
                print(f"[{ticker} 擷取失敗]: {e}")

        return results