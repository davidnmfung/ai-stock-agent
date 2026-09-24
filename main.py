import os
import time
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime

# ==================== 憑證與設定 ====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8894423509:AAF-pYhPtoW1kQeR8rLf0TwtcIw1tlCVLwA")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "852353260")

CORE_WATCHLIST = [
    "SMCX", "AIOT", "SOUN", "BBAI", "RGTI", "QUBT", "CRML", "GRML", "GLND", 
    "IONQ", "PLTR", "MARA", "RIOT", "CLSK", "SOFI", "UPST", "AFRM", "PATH", 
    "ASTS", "RKLB", "JOBY", "LUNR", "OKLO", "SMR", "NBIS"
]

# 策略門檻設定 (優化版：靈敏度提高)
MIN_RVOL = 1.3          # 放寬至 1.3 倍爆量
MIN_GAIN = 1.5          # 放寬至 +1.5% 漲幅
MAX_MA20_EXT = 0.25     # 放寬至 25% 均線延伸

DYNAMIC_SCREENER_LIMIT = 50  # 擴大動態飆股池至 50 檔
POLL_INTERVAL_SECONDS = 300  # 5 分鐘掃描一次
HOURLY_SUMMARY_INTERVAL = 12 # 每 12 輪 (1 小時) 發送一次盤中熱門摘要

# ==================== 功能函數 ====================

def send_telegram_message(message: str):
    """發送訊息至 Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ Telegram 發送失敗: {e}")

def get_dynamic_top_gainers(limit=DYNAMIC_SCREENER_LIMIT):
    """從 Yahoo Finance 擷取動態熱門飆股"""
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        params = {"scrIds": "day_gainers", "count": limit}
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, params=params, headers=headers, timeout=10)
        data = res.json()
        quotes = data.get("finance", {}).get("result", [{}])[0].get("quotes", [])
        
        # 篩選股價 <= 50 的飆股
        gainers = [q["symbol"] for q in quotes if q.get("regularMarketPrice", 999) <= 50]
        print(f"🔥 [動態熱門飆股篩選] 今日實時市場獲取 {len(gainers)} 檔大漲標的: {gainers}")
        return gainers
    except Exception as e:
        print(f"⚠️ 動態擷取熱門股失敗 (將僅使用核心 Watchlist): {e}")
        return []

def analyze_ticker(ticker: str):
    """分析單一股票的技術指標"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1mo", interval="1d")
        if len(df) < 20:
            return None
        
        latest_price = df['Close'].iloc[-1]
        open_price = df['Open'].iloc[-1]
        gain_pct = ((latest_price - open_price) / open_price) * 100
        
        # 計算 MA20 & RVOL
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        vol_avg_5d = df['Volume'].iloc[-6:-1].mean()
        curr_vol = df['Volume'].iloc[-1]
        rvol = (curr_vol / vol_avg_5d) if vol_avg_5d > 0 else 0
        
        # 爆發突破判斷
        is_breakout = (
            rvol >= MIN_RVOL and
            gain_pct >= MIN_GAIN and
            latest_price > ma20 and
            ((latest_price - ma20) / ma20) <= MAX_MA20_EXT
        )
        
        return {
            "ticker": ticker,
            "price": round(latest_price, 2),
            "gain_pct": round(gain_pct, 2),
            "rvol": round(rvol, 2),
            "ma20": round(ma20, 2),
            "is_breakout": is_breakout
        }
    except Exception:
        return None

def send_hourly_summary(metrics_list):
    """發送盤中熱門摘要 (每小時)"""
    if not metrics_list:
        return
    
    # 依漲幅與量能排序
    top_gainers = sorted(metrics_list, key=lambda x: x['gain_pct'], reverse=True)[:5]
    top_rvol = sorted(metrics_list, key=lambda x: x['rvol'], reverse=True)[:5]
    
    msg = "📊 *【AI Stock Agent - 盤中熱門標的心跳摘要】*\n"
    msg += f"⏰ 統計時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    msg += "🚀 *漲幅領先 Top 5:*\n"
    for item in top_gainers:
        msg += f"• `${item['ticker']}`: ${item['price']} | 漲幅: `{item['gain_pct']}%` | RVOL: `{item['rvol']}x`\n"
        
    msg += "\n🔥 *量能爆發 Top 5:*\n"
    for item in top_rvol:
        msg += f"• `${item['ticker']}`: ${item['price']} | RVOL: `{item['rvol']}x` | 漲幅: `{item['gain_pct']}%`\n"
        
    send_telegram_message(msg)

# ==================== 主流程迴圈 ====================

def main():
    print("🚀 AI Stock Agent 已啟動，開始於美股盤中常駐監控...")
    loop_count = 0
    
    while True:
        loop_count += 1
        print(f"\n🔍 [第 {loop_count} 輪掃描] 開始執行市場掃描...")
        
        # 1. 取得最新監控清單
        dynamic_gainers = get_dynamic_top_gainers()
        combined_list = list(dict.fromkeys(CORE_WATCHLIST + dynamic_gainers))
        print(f"📋 載入總監控清單 (共 {len(combined_list)} 檔): {combined_list}")
        
        breakout_signals = []
        all_metrics = []
        
        # 2. 逐一掃描股票
        for ticker in combined_list:
            res = analyze_ticker(ticker)
            if res:
                all_metrics.append(res)
                if res['is_breakout']:
                    breakout_signals.append(res)
        
        # 3. 處理即時突破預警
        if breakout_signals:
            msg = f"🚨 *AI 爆發股市場監控預警*\n\n當前共有 {len(breakout_signals)} 檔標的符合爆量突破條件：\n\n"
            for sig in breakout_signals:
                msg += f"• *${sig['ticker']}* | 價格: `${sig['price']}` | 漲幅: `+{sig['gain_pct']}%` | RVOL: `{sig['rvol']}x`\n"
                msg += f"  突破 MA20 均線，量能放大 {sig['rvol']} 倍，符合起漲訊號。\n\n"
            msg += f"⏰ 掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            send_telegram_message(msg)
            print("✅ 發現符合條件之爆發股，已發送 Telegram 預警！")
        else:
            print("ℹ️ 本輪掃描無符合條件之爆發股，暫不推播即時突破預警。")
            
        # 4. 每 12 輪 (1 小時) 推播盤中摘要報告
        if loop_count % HOURLY_SUMMARY_INTERVAL == 0:
            print("📊 發送每小時盤中熱門摘要報告...")
            send_hourly_summary(all_metrics)
            
        print(f"⌛ 等待 5 分鐘後進行下一次市場掃描...")
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()