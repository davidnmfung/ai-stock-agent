from datetime import datetime, timedelta
import json
import math
import os
import sys
import pytz
import requests
import yfinance as yf
from src.tracker import SignalTracker

# 初始化 SignalTracker
tracker = SignalTracker()

# ==================== 憑證與設定 ====================
RAW_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_BOT_TOKEN = (
    RAW_BOT_TOKEN[3:] if RAW_BOT_TOKEN.startswith("bot") else RAW_BOT_TOKEN
)

TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

CORE_WATCHLIST = [
    "SMCX", "AIOT", "SOUN", "BBAI", "RGTI", "QUBT", "CRML", "GRML", "GLND", "IONQ",
    "PLTR", "MARA", "RIOT", "CLSK", "SOFI", "UPST", "AFRM", "PATH", "ASTS", "RKLB",
    "JOBY", "LUNR", "OKLO", "SMR", "NBIS", "PPLI", "BIRK", "VECO", "FLY", "ABCL",
    "CAAP", "ALVO", "DFTX", "GAP", "AVPT", "AEO", "PACS", "WAY", "CCL", "MGNI"
]

# ==================== 量化篩選門檻 ====================
MIN_RVOL = 1.3  # 相對成交量比率 >= 1.3x
MIN_GAIN = 1.5  # 當日漲幅 >= 1.5%
MIN_DOLLAR_VOL = 10_000_000  # 最低成交金額 >= $10M
MIN_INTRADAY_LOC = 0.70  # 收盤/現價位居當日振幅 Top 30%
MIN_ATR_RATIO = 1.2  # 當日振幅達 14日平均 ATR 1.2倍以上


# ==================== 核心功能函數 ====================

def send_telegram_message(message: str):
    """發送訊息至 Telegram 群組"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ 錯誤: 缺少 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID Secrets。")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    MAX_CHAR = 3500
    chunks = [message[i : i + MAX_CHAR] for i in range(0, len(message), MAX_CHAR)]

    success = True
    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        try:
            res = requests.post(url, json=payload, timeout=10)
            res.raise_for_status()
        except Exception as e:
            print(f"❌ Telegram 發送失敗: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"   響應內容: {e.response.text}")
            success = False

    return success


def get_news(ticker: str):
    """Finnhub 最新新聞"""
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


def analyze_news_sentiment(ticker: str, news_items: list) -> dict:
    """利用 Gemini 1.5 Flash 進行新聞情緒與利多催化劑分析"""
    default_result = {"score": 5.0, "summary": "無顯著即時新聞催化劑"}
    if not GEMINI_API_KEY or not news_items:
        return default_result

    news_text = "\n".join([f"- {title}" for title, _ in news_items])
    prompt = f"""你是一位專業的美股量化分析師。請分析以下關於美股 ${ticker} 的最新新聞標題，評估其對個股當日爆量突破的利多強弱。

新聞列表：
{news_text}

請嚴格輸出符合以下格式的 JSON 物件（不要包含任何其他文字或 Markdown 標籤）：
{{
  "sentiment_score": 8.5,
  "catalyst_summary": "一句话繁體中文摘要，說明主要利多或利空原因"
}}

評分標準（1.0 ~ 10.0）：
- 1.0~4.0 分：利空或陷阱（例如：折價增發、股權稀釋、高管拋售、評級下調）。
- 5.0~6.5 分：中立或常規新聞（例如：一般市場觀點、無實質突破）。
- 7.0~10.0 分：強勁利多（例如：財報遠超預期、上調展望、重大商業訂單、FDA 批准）。
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }

    try:
        res = requests.post(url, json=payload, timeout=8)
        if res.status_code == 200:
            res_json = res.json()
            content_str = res_json["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(content_str)
            return {
                "score": round(float(data.get("sentiment_score", 5.0)), 1),
                "summary": data.get("catalyst_summary", "新聞解析完成"),
            }
    except Exception as e:
        print(f"⚠️ Gemini 新聞情緒分析異常 (${ticker}): {e}")

    return default_result


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
    """獲取單檔股票實時數據"""
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

        if (
            open_price == 0
            or math.isnan(latest_price)
            or math.isnan(open_price)
            or latest_price <= 0
        ):
            return None

        gain_pct = ((latest_price - open_price) / open_price) * 100
        vol_avg_5d = df["Volume"].iloc[-6:-1].mean()

        if math.isnan(gain_pct) or math.isnan(curr_vol):
            return None

        rvol = (curr_vol / vol_avg_5d) if vol_avg_5d > 0 else 0
        dollar_vol = latest_price * curr_vol

        day_range = day_high - day_low
        intraday_loc = (
            (latest_price - day_low) / day_range if day_range > 0 else 0.0
        )

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


# ==================== 報告產生邏輯 ====================

def run_top10_market_gainers_analysis():
    """全美股當日 Top 10 漲幅榜 + Gemini AI 催化劑解析"""
    top_tickers = fetch_top_market_gainers()
    if not top_tickers:
        return

    now_str = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y-%m-%d %H:%M:%S")
    msg = "🔥 *【全美股當日 Top 10 飆股榜 + Gemini AI 催化劑解析】*\n"
    msg += f"⏰ *統計時間*: {now_str}\n\n"

    for idx, ticker in enumerate(top_tickers, 1):
        data = fetch_stock_data(ticker)
        if not data:
            continue

        news_items = get_news(ticker)
        ai_res = analyze_news_sentiment(ticker, news_items)
        score = ai_res["score"]
        summary = ai_res["summary"]

        msg += f"*{idx}. ${data['ticker']}* | 價格: `${data['price']}` | 漲幅: `{data['gain_pct']}%` | RVOL: `{data['rvol']}x`\n"
        msg += f"   🧠 *Gemini AI 評分*: `{score}/10` — _{summary}_\n"
        if news_items:
            title, link = news_items[0]
            msg += f"   📰 [{title}]({link})\n"
        msg += "\n"

    send_telegram_message(msg)


def run_heartbeat_summary(stock_metrics):
    """盤中熱門標的心跳摘要 (基於核心監控清單)"""
    if not stock_metrics:
        return

    top_gainers = sorted(stock_metrics, key=lambda x: x["gain_pct"], reverse=True)[:5]
    top_rvols = sorted(stock_metrics, key=lambda x: x["rvol"], reverse=True)[:5]

    now_str = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y-%m-%d %H:%M:%S")

    msg = "📊 【AI Stock Agent - 核心清單心跳摘要】\n"
    msg += f"⏰ *統計時間*: {now_str}\n\n"

    msg += "🚀 *漲幅領先 Top 5*:\n"
    for s in top_gainers:
        msg += f"• *${s['ticker']}*: `${s['price']}` | 漲幅: `{s['gain_pct']}%` | RVOL: `{s['rvol']}x`\n"

    msg += "\n🔥 *量能爆發 Top 5*:\n"
    for s in top_rvols:
        msg += f"• *${s['ticker']}*: `${s['price']}` | RVOL: `{s['rvol']}x` | 漲幅: `{s['gain_pct']}%`\n"

    send_telegram_message(msg)


# ==================== 主執行流程 ====================

def main():
    print("🚀 [GitHub Actions] 開始執行美股掃描任務...")

    # 1. 執行核心 Watchlist 數據擷取與心跳摘要
    stock_metrics = []
    for ticker in CORE_WATCHLIST:
        data = fetch_stock_data(ticker)
        if data:
            stock_metrics.append(data)

    print(f"📊 成功擷取 {len(stock_metrics)} / {len(CORE_WATCHLIST)} 檔核心標的數據")
    if stock_metrics:
        run_heartbeat_summary(stock_metrics)

    # 2. 執行全美股當日 Top 10 飆股 + Gemini AI 分析
    run_top10_market_gainers_analysis()


if __name__ == "__main__":
    main()