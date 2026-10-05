import datetime
import pandas as pd
import yfinance as yf


def get_best_options(ticker_symbol: str):
    stock = yf.Ticker(ticker_symbol)
    try:
        expirations = stock.options
    except Exception:
        return None

    if not expirations:
        return None

    today = datetime.date.today()
    target_exp = None

    # 尋找到期日在 14 到 45 天之間的合約
    for exp in expirations:
        exp_date = datetime.datetime.strptime(exp, "%Y-%m-%d").date()
        dte = (exp_date - today).days
        if 14 <= dte <= 45:
            target_exp = exp
            break

    if not target_exp:
        target_exp = expirations[0]  # 若無符合天期，預設取最近到期日

    chain = stock.option_chain(target_exp)
    hist = stock.history(period="1d")
    current_price = hist["Close"].iloc[-1] if not hist.empty else 0

    if current_price == 0:
        return None

    # 1. 篩選最佳 Call (看漲權證，適用於像 PPLI 這類突破股)
    calls = chain.calls.copy()
    calls = calls[(calls["openInterest"] >= 100) & (calls["volume"] >= 50)]
    if not calls.empty:
        calls["spread_pct"] = (calls["ask"] - calls["bid"]) / calls["ask"]
        calls = calls[calls["spread_pct"] <= 0.15]
        # 尋找履約價最接近 OTM +2% 的 Call
        calls["strike_diff"] = (calls["strike"] - current_price * 1.02).abs()
        best_call = (
            calls.sort_values("strike_diff").iloc[0] if not calls.empty else None
        )
    else:
        best_call = None

    # 2. 篩選最佳 Put (看跌權證，適用於高位回檔股)
    puts = chain.puts.copy()
    puts = puts[(puts["openInterest"] >= 100) & (puts["volume"] >= 50)]
    if not puts.empty:
        puts["spread_pct"] = (puts["ask"] - puts["bid"]) / puts["ask"]
        puts = puts[puts["spread_pct"] <= 0.15]
        # 尋找履約價最接近 OTM -2% 的 Put
        puts["strike_diff"] = (puts["strike"] - current_price * 0.98).abs()
        best_put = (
            puts.sort_values("strike_diff").iloc[0] if not puts.empty else None
        )
    else:
        best_put = None

    return {
        "exp": target_exp,
        "call": best_call,
        "put": best_put,
        "price": current_price,
    }