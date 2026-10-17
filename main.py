from datetime import datetime
import pytz
from config.settings import CORE_WATCHLIST
from src.data_engine import fetch_top_market_gainers, fetch_stock_data, get_news
from src.strategy_engine import analyze_news_sentiment
from src.tracker import SignalTracker
from src.notifier import send_telegram_message

tracker = SignalTracker()

def run_top10_market_gainers_analysis():
    """全美股當日 Top 10 漲幅榜 + Gemini AI 催化劑解析 + 紀錄信號"""
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

        tracker.log_signal(
            ticker=data["ticker"],
            price=data["price"],
            gain_pct=data["gain_pct"],
            rvol=data["rvol"],
            ai_score=score,
            catalyst=summary
        )

        msg += f"*{idx}. ${data['ticker']}* | 價格: `${data['price']}` | 漲幅: `{data['gain_pct']}%` | RVOL: `{data['rvol']}x`\n"
        msg += f"   🧠 *Gemini AI 評分*: `{score}/10` — _{summary}_\n"
        if news_items:
            title, link = news_items[0]
            msg += f"   📰 [{title}]({link})\n"
        msg += "\n"

    history_summary = tracker.get_history_summary()
    msg += f"------------------\n{history_summary}"

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

def main():
    print("🚀 [GitHub Actions] 開始執行模組化美股掃描任務...")

    stock_metrics = []
    for ticker in CORE_WATCHLIST:
        data = fetch_stock_data(ticker)
        if data:
            stock_metrics.append(data)

    print(f"📊 成功擷取 {len(stock_metrics)} / {len(CORE_WATCHLIST)} 檔核心標的數據")
    if stock_metrics:
        run_heartbeat_summary(stock_metrics)

    run_top10_market_gainers_analysis()

if __name__ == "__main__":
    main()