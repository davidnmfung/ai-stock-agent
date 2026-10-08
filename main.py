from datetime import datetime, timedelta
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

# ==================== 量化篩選門檻 (Phase 1 升級) ====================
MIN_RVOL = 1.3  # 相對成交量比率 >= 1.3x
MIN_GAIN = 1.5  # 當日漲幅 >= 1.5%
MIN_DOLLAR_VOL = 10_000_000  # 最低成交金額 >= $10M (過濾低流動性陷阱)
MIN_INTRADAY_LOC = 0.70  # 收盤/現價需位居當日振幅 Top 30% (過濾長上影線)
MIN_ATR_RATIO = 1.2  # 當日振幅需達 14日平均 ATR 的 1.2 倍以上 (波動率真實擴張)


# ==================== 核心功能函數 ====================


def is_us_market_hours() -> bool:
  """判斷當前是否為美股常規交易時段（美東時間 09:30 - 16:00，週一至週五）"""
  tz = pytz.timezone("US/Eastern")
  now = datetime.now(tz)
  print(f"🕒 當前美東時間: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

  if now.weekday() >= 5:  # 週六 (5) 與週日 (6)
    print("💤 今日為週末，非美股交易日。")
    return False

  market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
  market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

  is_open = market_open <= now <= market_close
  if not is_open:
    print("💤 當前非美股交易時間 (09:30 - 16:00 EDT)。")
  return is_open


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


def calculate_signal_strength(
    rvol: float, short_float_val: float, atr_ratio: float
) -> str:
  """突破訊號強度試算（結合 RVOL、軋空率與 ATR 擴張度）"""
  if rvol >= 2.5 and atr_ratio >= 1.5:
    return "🔥 極強 (機構爆量/波動率強勢擴張)"
  elif rvol >= 1.8 or short_float_val >= 10.0:
    return "⚡ 強 (潛在軋空與動能標的)"
  elif rvol >= 1.3 and atr_ratio >= 1.2:
    return "⚡ 中高 (標準品質突破)"
  else:
    return "⚠ 中等 (符合邊界門檻，留意續航力)"


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

    type_str = (
        "(價內)"
        if strike < price
        else ("(價平)" if abs(strike - price) / price <= 0.03 else "(價外)")
    )
    return (
        f"  💡 *期權策略建議 (到期日 {target_exp})*: 首選 `${strike} Call`"
        f" {type_str} | 賣價 `${ask}` | 成交量 `{vol}`。\n"
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
  """獲取單檔股票實時數據（包含 ATR14、Dollar Volume 與 Intraday Location）"""
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

    # 計算 Intraday Location (當前價格處於當日高低振幅的比例)
    day_range = day_high - day_low
    intraday_loc = (
        (latest_price - day_low) / day_range if day_range > 0 else 0.0
    )

    # 計算 14-day ATR (True Range)
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


def run_breakout_scan(stock_metrics):
  """產生 🚨 爆發股市場監控預警 (套用進階技術面過濾器)"""
  breakout_signals = []
  for data in stock_metrics:
    # 嚴格驗證五大量化篩選指標
    if (
        data["rvol"] >= MIN_RVOL
        and data["gain_pct"] >= MIN_GAIN
        and data["dollar_vol"] >= MIN_DOLLAR_VOL
        and data["intraday_loc"] >= MIN_INTRADAY_LOC
        and data["atr_ratio"] >= MIN_ATR_RATIO
    ):

      enriched = get_enriched_info(data["ticker"])
      data["sector"] = enriched["sector"]
      data["market_cap"] = enriched["market_cap"]
      data["short_float"] = enriched["short_float"]
      data["short_float_val"] = enriched["short_float_val"]
      data["tv_url"] = enriched["tv_url"]
      data["finviz_url"] = enriched["finviz_url"]
      breakout_signals.append(data)

  if not breakout_signals:
    print(
        "ℹ️ 本輪未發現符合進階量化門檻 (RVOL>=1.3, Gain>=1.5%, $Vol>=$10M,"
        " Loc>=0.7, ATR_Ratio>=1.2) 之高品質突破標的。"
    )
    return

  tracker.log_signals(breakout_signals)

  msg = "🚨 *AI 高品質爆發股預警 (已過濾雜訊)*\n\n"
  msg += f"當前有 {len(breakout_signals)} 檔標的符合量化突破條件：\n\n"

  for sig in breakout_signals[:5]:
    t = sig["ticker"]
    p = sig["price"]
    g = sig["gain_pct"]
    r = sig["rvol"]
    d_vol_m = sig["dollar_vol"] / 1e6
    loc_pct = int(sig["intraday_loc"] * 100)
    atr_r = sig["atr_ratio"]

    strength = calculate_signal_strength(r, sig["short_float_val"], atr_r)
    opt_advice = get_best_options_advice(t, p)
    news_items = get_news(t)

    msg += f"• *${t}* | 價格: `${p}` | 漲幅: `{g}%` | RVOL: `{r}x`\n"
    msg += (
        f"  📊 *動能指標*: 成交額 `${d_vol_m:.1f}M` | 高點位置 `{loc_pct}%` |"
        f" ATR擴張 `{atr_r}x`\n"
    )
    msg += f"  🏷️ *基本面*: 板塊 `{sig['sector']}` | 市值 `{sig['market_cap']}`"
    if sig["short_float"] != "N/A":
      msg += f" | 做空率 `{sig['short_float']}`"
    msg += "\n"
    msg += f"  ⚡ *訊號品質*: {strength}\n"
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

  if send_telegram_message(msg):
    print(f"✅ 成功推播 {len(breakout_signals)} 檔高品質爆發股預警報告！")


def run_heartbeat_summary(stock_metrics):
  """產生 📊 盤中熱門標的心跳摘要"""
  if not stock_metrics:
    print("⚠️ 沒有可用的股票數據，跳過心跳摘要推播。")
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

  if send_telegram_message(msg):
    print("✅ 成功推播盤中熱門標的心跳摘要報告！")


# ==================== 主執行流程 ====================


def main():
  print("🚀 [GitHub Actions] 開始執行美股掃描任務...")

  if not is_us_market_hours():
    print("💤 非美股交易時間，跳過本輪掃描。")
    sys.exit(0)

  stock_metrics = []
  for ticker in CORE_WATCHLIST:
    data = fetch_stock_data(ticker)
    if data:
      stock_metrics.append(data)

  print(f"📊 成功擷取 {len(stock_metrics)} / {len(CORE_WATCHLIST)} 檔標的數據")

  if not stock_metrics:
    print("❌ 警告: 所有標的均未能取得數據，可能受到 Yahoo Finance Rate Limit 限制。")
    sys.exit(1)

  run_breakout_scan(stock_metrics)
  run_heartbeat_summary(stock_metrics)


if __name__ == "__main__":
  main()