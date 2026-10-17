from datetime import datetime, timedelta
import math
import requests
import yfinance as yf
from config.settings import FINNHUB_API_KEY

def fetch_top_market_gainers():
    """透過 Yahoo Finance 官方公開 API 抓取全美股當日真實 Top 10 漲幅榜"""
    print("🔍 正在檢索全美股市場當日真實 Top 10 飆股榜...")
    gainers_tickers = []
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds=day_gainers&count=10"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            quotes = data.get("finance", {}).get("result", [{}])[0].get("quotes", [])
            for q in quotes:
                symbol = q.get("symbol")
                if symbol and "." not in symbol and "-" not in symbol:
                    gainers_tickers.append(symbol)
    except Exception as e:
        print(f"⚠️ Yahoo Screener API 抓取失敗: {e}")

    if not gainers_tickers:
        gainers_tickers = ["PLTR", "NVDA", "TSLA", "AMD", "SMCI", "MARA", "COIN", "IONQ", "SOUN"]

    return gainers_tickers[:10]

def fetch_stock_data(ticker: str):
    """獲取單檔股票實時數據與技術指標計算"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2mo", interval="1d")
        if len(df) < 20:
            return None

        latest_price = df["Close"].iloc[-1]
        open_price = df["Open"].iloc[-1]
        day_high = df["High"].iloc[-1]
        day_low = df["Low"].iloc[-1]
        curr_vol = df["Volume"].iloc[-1]

        if open_price == 0 or math.isnan(latest_price) or math.isnan(open_price) or latest_price <= 0:
            return None

        gain_pct = ((latest_price - open_price) / open_price) * 100
        vol_avg_5d = df["Volume"].iloc[-6:-1].mean()

        if math.isnan(gain_pct) or math.isnan(curr_vol):
            return None

        rvol = (curr_vol / vol_avg_5d) if vol_avg_5d > 0 else 0
        dollar_vol = latest_price * curr_vol

        day_range = day_high - day_low
        intraday_loc = (latest_price - day_low) / day_range if day_range > 0 else 0.0

        df["prev_close"] = df["Close"].shift(1)
        df["tr1"] = df["High"] - df["Low"]
        df["tr2"] = (df["High"] - df["prev_close"]).abs()
        df["tr3"] = (df["Low"] - df["prev_close"]).abs()
        df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
        atr14 = df["tr"].iloc[-15:-1].mean()

        atr_ratio = (day_range / atr14) if (atr14 and atr14 > 0) else 0.0

        return {
            "ticker": ticker,
            "price": round(latest_price, 2),
            "gain_pct": round(gain_pct, 2),
            "rvol": round(rvol, 2),
            "dollar_vol": round(dollar_vol, 0),
            "intraday_loc": round(intraday_loc, 2),
            "atr_ratio": round(atr_ratio, 2),
        }
    except Exception as e:
        print(f"⚠️ 無法取得 {ticker} 數據: {e}")
        return None

def get_news(ticker: str):
    """Finnhub 最新新聞擷取"""
    news_list = []
    if not FINNHUB_API_KEY:
        return news_list

    try:
        today = datetime.now().date()
        today_str = today.strftime("%Y-%m-%d")
        from_str = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from_str}&to={today_str}&token={FINNHUB_API_KEY}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            for item in res.json()[:3]:
                title = (
                    item.get("headline", "")
                    .replace("*", "")
                    .replace("_", "")
                    .replace("`", "")
                    .replace("[", "")
                    .replace("]", "")
                )
                url_link = item.get("url", "")
                if title and url_link:
                    news_list.append((title, url_link))
    except Exception:
        pass
    return news_list