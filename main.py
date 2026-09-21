import time
from data.fetcher import StockFetcher
from agents.catalyst import CatalystAgent
from agents.risk import RiskAgent
from notifications.telegram_bot import TelegramNotifier

# 紀錄已推播標的與時間，避免短時間內重複發送推播
triggered_history = {}
COOLDOWN_SECONDS = 3600  # 同一檔股票 1 小時內不重複預警


def run_pipeline():
    fetcher = StockFetcher()
    catalyst = CatalystAgent()
    risk_agent = RiskAgent()
    notifier = TelegramNotifier()

    print("\n🚀 執行 AI Stock Agent 市場掃描...")
    stocks = fetcher.get_top_gainers_or_surges()
    current_time = time.time()

    for stock in stocks:
        ticker = stock["ticker"]
        price = stock["price"]
        rvol = stock["rvol"]
        market_cap = stock["market_cap"]

        # 1. 催化劑分析
        cat_analysis = catalyst.analyze_catalyst(ticker, price, rvol)
        score = cat_analysis.get("score", 0)
        reason = cat_analysis.get("reason", "")

        # 2. 風控審核
        passed_risk = risk_agent.evaluate_risk(
            ticker, price, rvol, market_cap
        )

        # 3. 檢查冷卻時間（防止洗版）
        last_triggered = triggered_history.get(ticker, 0)
        in_cooldown = (current_time - last_triggered) < COOLDOWN_SECONDS

        # 4. 門檻觸發與推播
        if score >= 7 and passed_risk:
            if in_cooldown:
                print(
                    f"  [冷卻中] ${ticker} 符合預警，但處於 1 小時冷卻期內，暫不重複推播。"
                )
            else:
                msg = f"🚀 *AI 爆發股預警*\n\n標的: `${ticker}`\n價格: `${price}`\nRVOL: `{rvol}x`\nAI 評分: `{score}/10`\n\n💡 *分析*: {reason}"
                if notifier.send_message(msg):
                    triggered_history[ticker] = current_time
                    print(
                        f"✅ [Telegram] ${ticker} 預警訊息已成功推播至手機！"
                    )
        else:
            print(
                f"  [攔截] ${ticker} 未達預警門檻 (催化劑: {score}分, 風控: {passed_risk})"
            )


if __name__ == "__main__":
    print(
        "🤖 AI Stock Agent 已啟動，開始於美股盤中常駐監控（每 5 分鐘自動掃描一次）..."
    )
    while True:
        try:
            run_pipeline()
        except Exception as e:
            print(f"⚠️ 執行過程發生異常: {e}")

        print(
            "\n⏳ 等待 5 分鐘後進行下一次市場掃描... (可按 Ctrl + C 停止運行)"
        )
        time.sleep(300)