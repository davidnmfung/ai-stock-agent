import os
import time
from datetime import datetime, timedelta
import pandas as pd
import requests
import yfinance as yf

# ==================== 憑證與設定 ====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8894423509:AAF-pYhPtoW1kQeR8rLf0TwtcIw1tlCVLwA")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-5190891893")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "dassh7hr01qm680ge2kgdassh7hr01qm680ge2l0")

CORE_WATCHLIST = [
    "SMCX", "AIOT", "SOUN", "BBAI", "RGTI", "QUBT", "CRML", "GRML", "GLND", "IONQ", 
    "PLTR", "MARA", "RIOT", "CLSK", "SOFI", "UPST", "AFRM", "PATH", "ASTS", "RKLB", 
    "JOBY", "LUNR", "OKLO", "SMR", "NBIS", "PPLI", "BIRK"
]

# 策略門檻設定
MIN_RVOL = 1.3        # 1.3 倍爆量
MIN_GAIN = 1.5        # +1.5% 漲幅
MAX_MA20_EXT = 0.25   # 25% 均線延伸

DYNAMIC_SCREENER_LIMIT = 50   # 動態飆股池 50 檔
POLL_INTERVAL_SECONDS = 300    # 5 分鐘掃描一次
SUMMARY_INTERVAL_LOOPS = 24    # 每 24 輪 (約 2 小時) 發送一次熱門摘要

# 紀錄當日已預警過的股票
alerted_today = set()
current_date = datetime.now().date()

# ==================== 功能函數 ====================

def send_telegram_message(message: str):
    """發送訊息至 Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True  # 避免多條連結預覽畫面太佔空間
    }
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
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, params=params, headers=headers, timeout=10)
        data = res.json()
        quotes = data.get('finance', {}).get('result', [{}])[0].get('quotes', [])
        
        gainers = [q['symbol'] for q in quotes if q.get('regularMarketPrice', 999) <= 50]
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
        
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        vol_avg_5d = df['Volume'].iloc[-6:-1].mean()
        curr_vol = df['Volume'].iloc[-1]
        rvol = (curr_vol / vol_avg_5d) if vol_avg_5d > 0 else 0
        
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

def get_enriched_info(ticker_symbol: str):
    """抓取市值、板塊、做空比例等補充交易資訊 (帶完整容錯)"""
    info_data = {
        "sector": "N/A",
        "market_cap": "N/A",
        "short_float": "N/A",
        "short_float_val": 0.0,
        "tv_url": f"https://www.tradingview.com/chart/?symbol={ticker_symbol}",
        "finviz_url": f"https://finviz.com/quote.ashx?t={ticker_symbol}"
    }
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info or {}
        
        # 板塊
        info_data["sector"] = info.get("sector", "N/A")
        
        # 市值格式化 ($B / $M)
        mc = info.get("marketCap")
        if mc:
            if mc >= 1e9:
                info_data["market_cap"] = f"${mc / 1e9:.2f}B"
            elif mc >= 1e6:
                info_data["market_cap"] = f"${mc / 1e6:.1f}M"
            else:
                info_data["market_cap"] = f"${mc:,.0f}"
                
        # 做空比例 (Short Percent of Float)
        sf = info.get("shortPercentOfFloat")
        if sf is not None:
            val = round(sf * 100, 1)
            info_data["short_float_val"] = val
            info_data["short_float"] = f"{val}%"
            
    except Exception as e:
        print(f"⚠️ 擷取 {ticker_symbol} 基本面資訊失敗: {e}")
        
    return info_data

def calculate_signal_strength(rvol: float, short_float_val: float) -> str:
    """自動計算突破訊號強度"""
    if rvol >= 2.5 or (rvol >= 1.8 and short_float_val >= 10.0):
        return "🔥 極強 (機構爆量/軋空雙驅動)"
    elif rvol >= 1.8 or short_float_val >= 10.0:
        return "⚡ 強 (動能起漲標的)"
    elif rvol >= 1.5:
        return "⚡ 中高 (標準突破)"
    else:
        return "⚠️ 中等 (邊界訊號，留意量能延續性)"

def get_best_options(ticker_symbol: str):
    """自動篩選流動性良好且天期合適的首選 Call 期權"""
    try:
        stock = yf.Ticker(ticker_symbol)
        expirations = stock.options
        if not expirations:
            return None
        
        today = datetime.now().date()
        target_exp = None
        
        for exp in expirations:
            exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
            dte = (exp_date - today).days
            if 14 <= dte <= 45:
                target_exp = exp
                break
                
        if not target_exp:
            target_exp = expirations[0]
            
        chain = stock.option_chain(target_exp)
        hist = stock.history(period="1d")
        current_price = hist['Close'].iloc[-1] if not hist.empty else 0
        
        if current_price == 0:
            return None
            
        calls = chain.calls.copy()
        calls = calls[(calls['openInterest'] >= 100) & (calls['volume'] >= 50)]
        best_call = None
        if not calls.empty:
            calls['spread_pct'] = (calls['ask'] - calls['bid']) / calls['ask']
            calls = calls[calls['spread_pct'] <= 0.15]
            if not calls.empty:
                calls['strike_diff'] = (calls['strike'] - current_price * 1.02).abs()
                best_call = calls.sort_values('strike_diff').iloc[0].to_dict()
                
        return {"exp": target_exp, "call": best_call}
    except Exception as e:
        print(f"⚠️ 期權數據擷取失敗 ({ticker_symbol}): {e}")
        return None

def get_option_strategy_advice(price: float, opt_data: dict) -> str:
    """根據期權數據自動產出『期權策略建議 (到期日 10-16)』"""
    if not opt_data or not opt_data.get('call'):
        return "💡 *期權策略建議 (到期日 10-16)*: 無合適期權或流動性不足，建議以現貨分批佈局為主。"
    
    c = opt_data['call']
    exp = opt_data['exp']
    strike = c['strike']
    ask = c['ask']
    vol = int(c['volume'])
    
    if strike < price:
        return f"💡 *期權策略建議 (到期日 {exp})*: 首選 `${strike} Call` (價內) | 賣價 `${ask}` | 成交量 `{vol}`。Delta 較高，保護性好，適合鎖定波段漲幅。"
    elif abs(strike - price) / price <= 0.03:
        return f"💡 *期權策略建議 (到期日 {exp})*: 首選 `${strike} Call` (價平) | 賣價 `${ask}` | 成交量 `{vol}`。權利金適中，適合小資金博短線爆發。"
    else:
        return f"💡 *期權策略建議 (到期日 {exp})*: 首選 `${strike} Call` (價外) | 賣價 `${ask}` | 成交量 `{vol}`。槓桿較大，需留意倒數時間價值 (Theta) 衰退風險。"

def get_earnings_and_news(ticker_symbol: str):
    """使用 Finnhub API 穩定獲取財報日與最新 3 則新聞（含超連結）"""
    is_earnings_near = False
    earnings_msg = ""
    news_list = []
    
    try:
        today = datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')
        from_date_str = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # 1. 擷取新聞 (Finnhub API)
        news_url = f"https://finnhub.io/api/v1/company-news?symbol={ticker_symbol}&from={from_date_str}&to={today_str}&token={FINNHUB_API_KEY}"
        res_news = requests.get(news_url, timeout=5)
        if res_news.status_code == 200:
            news_data = res_news.json()
            for item in news_data[:3]:
                headline = item.get("headline", "")
                article_url = item.get("url", "")
                if headline and article_url:
                    clean_title = (
                        headline.replace("*", "")
                        .replace("_", "")
                        .replace("`", "")
                        .replace("[", "")
                        .replace("]", "")
                    )
                    news_list.append({"title": clean_title, "url": article_url})

        # 2. 擷取財報日日曆 (Finnhub API)
        future_date_str = (today + timedelta(days=30)).strftime('%Y-%m-%d')
        cal_url = f"https://finnhub.io/api/v1/calendar/earnings?from={today_str}&to={future_date_str}&symbol={ticker_symbol}&token={FINNHUB_API_KEY}"
        res_cal = requests.get(cal_url, timeout=5)
        if res_cal.status_code == 200:
            cal_data = res_cal.json().get("earningsCalendar", [])
            if cal_data:
                next_earnings_str = cal_data[0].get("date")
                if next_earnings_str:
                    next_earnings = datetime.strptime(next_earnings_str, "%Y-%m-%d").date()
                    days_diff = (next_earnings - today).days
                    
                    if 0 <= days_diff <= 7:
                        is_earnings_near = True
                        earnings_msg = f"⚠️ *EARNINGS WARNING*: 財報將於 {days_diff} 天內 ({next_earnings}) 發布！注意 IV Crush 風險。"
                    elif days_diff > 7:
                        earnings_msg = f"📅 下次財報日: {next_earnings} (尚餘 {days_diff} 天)"

    except Exception as e:
        print(f"⚠️ Finnhub 數據擷取失敗 ({ticker_symbol}): {e}")

    return is_earnings_near, earnings_msg, news_list

def send_summary(metrics_list):
    """發送盤中熱門摘要報告 (每 2 小時)"""
    if not metrics_list:
        return

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
    global current_date, alerted_today
    print("🚀 AI Stock Agent 已啟動，開始於美股盤中常駐監控...")
    loop_count = 0

    while True:
        loop_count += 1
        today = datetime.now().date()
        
        if today != current_date:
            print("🌅 新的一天，重置當日已發送預警清單...")
            alerted_today.clear()
            current_date = today

        print(f"\n🔍 [第 {loop_count} 輪掃描] 開始執行市場掃描...")
        
        dynamic_gainers = get_dynamic_top_gainers()
        combined_list = list(dict.fromkeys(CORE_WATCHLIST + dynamic_gainers))
        print(f"📋 載入總監控清單 (共 {len(combined_list)} 檔): {combined_list}")
        
        breakout_signals = []
        all_metrics = []

        for ticker in combined_list:
            res = analyze_ticker(ticker)
            if res:
                all_metrics.append(res)
                if res['is_breakout'] and (ticker not in alerted_today):
                    breakout_signals.append(res)

        if breakout_signals:
            msg = f"🚨 *AI 爆發股市場監控預警 (新起漲標的)*\n\n當前有 {len(breakout_signals)} 檔新標的符合爆量突破條件：\n\n"
            for sig in breakout_signals:
                ticker = sig['ticker']
                price = sig['price']
                rvol = sig['rvol']
                
                # 1. 補充基本面資料
                enriched = get_enriched_info(ticker)
                
                # 2. 計算突破訊號強度
                strength = calculate_signal_strength(rvol, enriched['short_float_val'])
                
                msg += f"• *${ticker}* | 價格: `${price}` | 漲幅: `+{sig['gain_pct']}%` | RVOL: `{rvol}x`\n"
                msg += f"  🏷️ *基本面*: 板塊 `{enriched['sector']}` | 市值 `{enriched['market_cap']}`"
                if enriched['short_float'] != "N/A":
                    msg += f" | 做空率 `{enriched['short_float']}`"
                msg += "\n"
                
                msg += f"  ⚡ *突破訊號強度*: {strength}\n"
                
                # 3. 期權資料與策略建議
                opt = get_best_options(ticker)
                opt_advice = get_option_strategy_advice(price, opt)
                msg += f"  {opt_advice}\n"
                
                # 4. 財報日與新聞
                is_near, earnings_info, news_list = get_earnings_and_news(ticker)
                if earnings_info:
                    msg += f"  {earnings_info}\n"
                if news_list:
                    msg += "  📰 *最新新聞*:\n"
                    for news in news_list:
                        msg += f"    • [{news['title']}]({news['url']})\n"
                
                # 5. 快捷圖表連結
                msg += f"  🔗 [📈 TradingView 圖表]({enriched['tv_url']}) | [📊 Finviz 分析]({enriched['finviz_url']})\n"
                msg += "\n"
                
                alerted_today.add(ticker)

            msg += f"⏰ 掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            send_telegram_message(msg)
            print(f"✅ 發現 {len(breakout_signals)} 檔新爆發股，已發送 Telegram 預警！")
        else:
            print("ℹ️ 本輪無新符合條件之爆發股（或已於今日預警過），維持靜音。")

        if loop_count % SUMMARY_INTERVAL_LOOPS == 0:
            print("📊 發送每 2 小時盤中熱門摘要報告...")
            send_summary(all_metrics)

        print("⌛ 等待 5 分鐘後進行下一次市場掃描...")
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()