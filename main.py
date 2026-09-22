import json
import math
import os
import time
from agents.catalyst import CatalystAgent
from agents.risk import RiskAgent
from data.fetcher import StockFetcher
from notifications.telegram_bot import TelegramNotifier

# 紀錄已推播標的與時間，避免短時間內重複發送推播
triggered_history = {}
COOLDOWN_SECONDS = 3600  # 同一檔股票 1 小時內不重複預警
WATCHLIST_PATH = os.path.join("config", "watchlist.json")


def load_watchlist():
    """嘗試讀取 config/watchlist.json 中的股票清單，若不存在則回傳 None"""
    if os.path.exists(WATCHLIST_PATH):
        try:
            with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                tickers = data.get("watchlist", [])
                if tickers:
                    return tickers
        except Exception as e:
            print(f"⚠️ 讀取 {WATCHLIST_PATH} 失敗: {e}")
    return None


def run_pipeline(fetcher, catalyst, risk_agent, notifier):
    print("\n🚀 執行 AI Stock Agent 市場掃描...")

    # 1. 檢查並載入動態 Watchlist（若有 config/watchlist.json 則優先使用）
    custom_tickers = load_watchlist()

    try:
        if custom_tickers:
            print(
                f"📋 載入自訂 Watchlist 清單 ({len(custom_tickers)} 檔):"
                f" {custom_tickers}"
            )
            stocks = fetcher.get_top_gainers_or_surges(
                custom_tickers=custom_tickers
            )
        else:
            stocks = fetcher.get_top_gainers_or_surges()
    except Exception as e:
        print(f"⚠️ 抓取市場數據失敗: {e}")
        return

    current_time = time.time()

    for stock in stocks:
        ticker = stock.get("ticker", "UNKNOWN")
        price = stock.get("price")
        rvol = stock.get("rvol", 0)
        market_cap = stock.get("market_cap", 0)

        # 2. 數據有效性檢查（防止 yfinance HTTP 429 回傳 NaN 造成錯誤風控判斷）
        if price is None or (isinstance(price, float) and math.isnan(price)):
            print(f"  [數據異常] ${ticker} 價格無效 (NaN)，跳過本次檢查。")
            continue

        # 3. 催化劑分析
        cat_analysis = catalyst.analyze_catalyst(ticker, price, rvol)
        score = cat_analysis.get("score", 0)
        reason = cat_analysis.get("reason", "")

        # 4. 風控審核
        passed_risk = risk_agent.evaluate_risk(
            ticker, price, rvol, market_cap
        )

        # 5. 檢查冷卻時間（防止洗版）
        last_triggered = triggered_history.get(ticker, 0)
        in_cooldown = (current_time - last_triggered) < COOLDOWN_SECONDS

        # 6. 門檻觸發與推播
        if score >= 7 and passed_risk:
            if in_cooldown:
                print(
                    f"  [冷卻中] ${ticker} 符合預警，但處於 1 小時冷卻期內，暫不重複推播。"
                )
            else:
                msg = (
                    f"🚀 *AI 爆發股預警*\n\n"
                    f"標的: `${ticker}`\n"
                    f"價格: `${price}`\n"
                    f"RVOL: `{rvol}x`\n"
                    f"AI 評分: `{score}/10`\n\n"
                    f"💡 *分析*: {reason}"
                )
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

    # 初始化模組（重複利用 Session）
    fetcher = StockFetcher()
    catalyst = CatalystAgent()
    risk_agent = RiskAgent()
    notifier = TelegramNotifier()

    while True:
        try:
            run_pipeline(fetcher, catalyst, risk_agent, notifier)
        except KeyboardInterrupt:
            print("\n👋 手動終止程序，常駐監控已停止。")
            break
        except Exception as e:
            print(f"⚠️ 執行過程發生異常: {e}")

        print(
            "\n⏳ 等待 5 分鐘後進行下一次市場掃描... (可按 Ctrl + C 停止運行)"
        )
        time.sleep(300)