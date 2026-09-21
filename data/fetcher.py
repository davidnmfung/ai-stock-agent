import requests
import yfinance as yf


class StockFetcher:

    def __init__(self):
        self.tickers = [
            "SMCX",
            "AIOT",
            "SOUN",
            "BBAI",
            "RGTI",
            "QUBT",
        ]

    def get_top_gainers_or_surges(self):
        results = []

        # 建立帶有標準瀏覽器 User-Agent 的 Session，防止被 Yahoo 雲端封鎖
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                " AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/120.0.0.0 Safari/537.36"
            )
        })

        for ticker_symbol in self.tickers:
            try:
                ticker = yf.Ticker(ticker_symbol, session=session)
                df = ticker.history(period="5d")

                if df.empty or len(df) < 2:
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

                market_cap = 0
                try:
                    market_cap = (
                        ticker.info.get("marketCap", 0)
                        if ticker.info
                        else 0
                    )
                except Exception:
                    pass

                results.append({
                    "ticker": ticker_symbol,
                    "price": price,
                    "rvol": rvol,
                    "market_cap": market_cap,
                })
            except Exception as e:
                print(f"[{ticker_symbol} 擷取失敗]: {e}")

        return results