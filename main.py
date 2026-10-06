from datetime import datetime, timedelta
import math
import os
import sys
import pytz
import requests
from src.tracker import SignalTracker
import yfinance as yf

# 初始化 SignalTracker
tracker = SignalTracker()

# ==================== 憑證與設定 ====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

CORE_WATCHLIST = [
    "SMCX",
    "AIOT",
    "SOUN",
    "BBAI",
    "RGTI",
    "QUBT",
    "CRML",
    "GRML",
    "GLND",
    "IONQ",
    "PLTR",
    "MARA",
    "RIOT",
    "CLSK",
    "SOFI",
    "UPST",
    "AFRM",
    "PATH",
    "ASTS",
    "RKLB",
    "JOBY",
    "LUNR",
    "OKLO",
    "SMR",
    "NBIS",
    "PPLI",
    "BIRK",
    "VECO",
    "FLY",
    "ABCL",
    "CAAP",
    "ALVO",
    "DFTX",
    "GAP",
    "AVPT",
    "AEO",
    "PACS",
    "WAY",
    "CCL",
    "MGNI",
]

MIN_RVOL = 1.3  # RVOL ≥ 1.3x 爆量
MIN_GAIN = 1.5  # 漲幅 ≥ +1.5%


# ==================== 核心功能函數 ====================


def is_us_market_hours() -> bool:
  """判斷是否為美股交易時段（🧪 強制測試模式：永遠返回 True）"""
  return True


def send_telegram_message(message: str):
  """發送訊息至 Telegram 群組"""
  if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("❌ 缺少 Telegram 憑證，無法發送訊息。")
    return

  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  MAX_CHAR = 3500
  chunks = [message[i : i + MAX_CHAR] for i in range(0, len(message), MAX_CHAR)]

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


def get_enriched_info(ticker: str):
  """基本面數據（板塊、市值、做空率）"""
  info_data = {
      "sector": "N/A",
      "market_cap": "N/A",
      "short_float": "N/A",
      "short_float_val": 0.0,
      "tv_url": f"https://www.tradingview.com/chart/?symbol={ticker}",
      "finviz_url": f"https://finviz.com/quote.ashx?t={ticker}",
  }
  try:
    stock = yf.Ticker(ticker)
    info = stock.info or {}
    info_data["sector"] = info.get("sector", "N/A")

    mc = info.get("marketCap")
    if mc and isinstance(mc, (int, float)) and not math.isnan(mc):
      if mc >= 1e9:
        info_data["market_cap"] = f"${mc / 1e9:.2f}B"
      elif mc >= 1e6:
        info_data["market_cap"] = f"${mc / 1e6:.1f}M"
      else:
        info_data["market_cap"] = f"${mc:,.0f}"

    sf = info.get("shortPercentOfFloat")
    if sf is not None and isinstance(sf, (int, float)) and not math.isnan(sf):
      val = round(sf * 100, 1)
      info_data["short_float_val"] = val
      info_data["short_float"] = f"{val}%"
  except Exception:
    pass
  return info_data


def calculate_signal_strength(rvol: float, short_float_val: float) -> str:
  """突破訊號強度試算"""
  if rvol >= 2.5 or (rvol >= 1.8 and short_float_val >= 10.0):
    return "🔥 極強 (機構爆量/軋空雙驅動)"
  elif rvol >= 1.8 or short_float_val >= 10.0:
    return "⚡ 強 (動能起漲標的)"
  elif rvol >= 1.5:
    return "⚡ 中高 (標準突破)"
  else:
    return "⚠ 中等 (邊界訊號，留意量能延續性)"


def get_best_options_advice(ticker: str, price: float) -> str:
  """首選 Call 期權建議"""
  try:
    stock = yf.Ticker(ticker)
    expirations = stock.options
    if not expirations:
      return ""

    today = datetime.now().date()
    target_exp = None
    for exp in expirations:
      exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
      if 14 <= (exp_date - today).days <= 45:
        target_exp = exp
        break
    if not target_exp:
      target_exp = expirations[0]

    chain = stock.option_chain(target_exp)
    calls = chain.calls.copy()
    if calls.empty:
      return ""

    calls["strike_diff"] = (calls["strike"] - price * 1.02).abs()
    best_call = calls.sort_values("strike_diff").iloc[0]

    strike = best_call["strike"]
    ask = round(best_call["ask"], 2)
    vol = (
        int(best_call["volume"])
        if not math.isnan(best_call.get("volume", 0))
        else 0
    )

    if strike < price:
      type_str = "(價內)"
      advice = "Delta 較高，保護性好，適合鎖定波段漲幅。"
    elif abs(strike - price) / price <= 0.03:
      type_str = "(價平)"
      advice = "權利金適中，適合小資金博短線爆發。"
    else:
      type_str = "(價外)"
      advice = "槓桿較大，需留意倒數時間價值 (Theta) 衰退風險。"

    return (
        f"  💡 *期權策略建議 (到期日 {target_exp})*: 首選 `${strike} Call`"
        f" {type_str} | 賣價 `${ask}` | 成交量 `{vol}`。{advice}\n"
    )
  except Exception:
    return ""


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


def fetch_stock_data(ticker: str):
  """獲取單檔股票實時數據（防 NaN 機制）"""
  try:
    stock = yf.Ticker(ticker)
    df = stock.history(period="1mo", interval="1d")
    if len(df) < 20:
      return None

    latest_price = df["Close"].iloc[-1]
    open_price = df["Open"].iloc[-1]

    if (
        open_price == 0
        or math.isnan(latest_price)
        or math.isnan(open_price)
        or latest_price <= 0
    ):
      return None

    gain_pct = ((latest_price - open_price) / open_price) * 100
    vol_avg_5d = df["Volume"].iloc[-6:-1].mean()
    curr_vol = df["Volume"].iloc[-1]

    if math.isnan(gain_pct) or math.isnan(curr_vol):
      return None

    rvol = (curr_vol / vol_avg_5d) if vol_avg_5d > 0 else 0

    return {
        "ticker": ticker,
        "price": round(latest_price, 2),
        "gain_pct": round(gain_pct, 2),
        "rvol": round(rvol, 2),
    }
  except Exception:
    return None


# ==================== 報告產生邏輯 ====================


def run_breakout_scan(stock_metrics):
  """產生 🚨 爆發股市場監控預警"""
  breakout_signals = []
  for data in stock_metrics:
    if data["rvol"] >= MIN_RVOL and data["gain_pct"] >= MIN_GAIN:
      enriched = get_enriched_info(data["ticker"])
      data["sector"] = enriched["sector"]
      data["market_cap"] = enriched["market_cap"]
      data["short_float"] = enriched["short_float"]
      data["short_float_val"] = enriched["short_float_val"]
      data["tv_url"] = enriched["tv_url"]
      data["finviz_url"] = enriched["finviz_url"]
      breakout_signals.append(data)

  if not breakout_signals:
    print("ℹ️ 本輪未發現符合門檻 (RVOL≥1.3 & 漲幅≥1.5%) 之爆量突破標的。")
    return

  # 1. 寫入歷史 Signal 紀錄庫 (用於 Forward Testing)
  tracker.log_signals(breakout_signals)

  # 2. 組合 Telegram 訊息格式並推播
  msg = "🚨 *AI 爆發股市場監控預警 (新起漲標的)*\n\n"
  msg += f"當前有 {len(breakout_signals)} 檔新標的符合爆量突破條件：\n\n"

  for sig in breakout_signals:
    t = sig["ticker"]
    p = sig["price"]
    g = sig["gain_pct"]
    r = sig["rvol"]

    strength = calculate_signal_strength(r, sig["short_float_val"])
    opt_advice = get_best_options_advice(t, p)
    news_items = get_news(t)

    msg += f"• *${t}* | 價格: `${p}` | 漲幅: `+{g}%` | RVOL: `{r}x`\n"
    msg += "  突破 MA20 均線，量能放大" f" {r} 倍，符合起漲訊號。\n"
    msg += (
        f"  🏷️ *基本面*: 板塊 `{sig['sector']}` | 市值"
        f" `{sig['market_cap']}`"
    )
    if sig["short_float"] != "N/A":
      msg += f" | 做空率 `{sig['short_float']}`"
    msg += "\n"
    msg += f"  ⚡ *突破訊號強度*: {strength}\n"
    if opt_advice:
      msg += opt_advice

    if news_items:
      msg += "  📰 *最新新聞*:\n"
      for title, n_url in news_items:
        msg += f"    • [{title}]({n_url})\n"

    msg += (
        f"  🔗 [📈 TradingView 圖表]({sig['tv_url']}) | [📊"
        f" Finviz 分析]({sig['finviz_url']})\n\n"
    )

  now_str = datetime.now(pytz.timezone("US/Eastern")).strftime(
      "%Y-%m-%d %H:%M:%S"
  )
  msg += f"⏰ *掃描時間*: {now_str}"

  send_telegram_message(msg)
  print(f"✅ 成功推播 {len(breakout_signals)} 檔爆發股預警報告並紀錄至歷史資料庫！")


def run_heartbeat_summary(stock_metrics):
  """產生 📊 盤中熱門標的心跳摘要"""
  if not stock_metrics:
    return

  top_gainers = sorted(stock_metrics, key=lambda x: x["gain_pct"], reverse=True)[
      :5
  ]
  top_rvols = sorted(stock_metrics, key=lambda x: x["rvol"], reverse=True)[:5]

  now_str = datetime.now(pytz.timezone("US/Eastern")).strftime(
      "%Y-%m-%d %H:%M:%S"
  )

  msg = "📊 【AI Stock Agent - 盤中熱門標的心跳摘要】\n"
  msg += f"⏰ *統計時間*: {now_str}\n\n"

  msg += "🚀 *漲幅領先 Top 5*:\n"
  for s in top_gainers:
    msg += (
        f"• *${s['ticker']}*: `${s['price']}` | 漲幅: `{s['gain_pct']}%` | RVOL:"
        f" `{s['rvol']}x`\n"
    )

  msg += "\n🔥 *量能爆發 Top 5*:\n"
  for s in top_rvols:
    msg += (
        f"• *${s['ticker']}*: `${s['price']}` | RVOL: `{s['rvol']}x` | 漲幅:"
        f" `{s['gain_pct']}%`\n"
    )

  send_telegram_message(msg)
  print("✅ 成功推播盤中熱門標的心跳摘要報告！")


# ==================== 主執行流程 ====================


def main():
  print("🚀 [GitHub Actions] 開始執行美股掃描任務 (測試模式)...")

  if not is_us_market_hours():
    print("💤 當前非美股交易時間，跳過本輪掃描。")
    sys.exit(0)

  stock_metrics = []
  for ticker in CORE_WATCHLIST:
    data = fetch_stock_data(ticker)
    if data:
      stock_metrics.append(data)

  # 1. 執行爆發股突破檢查並記錄 Signal
  run_breakout_scan(stock_metrics)

  # 2. 強制測試：直接發送心跳摘要報告
  run_heartbeat_summary(stock_metrics)


if __name__ == "__main__":
  main()