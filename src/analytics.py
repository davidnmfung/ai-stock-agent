import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

def run_performance_analytics(csv_path="data/signal_history.csv"):
    """
    Reads signal history and calculates forward return metrics (T+1, T+3, T+5)
    and overall win-rate for the AI stock agent.
    """
    if not os.path.exists(csv_path):
        print(f"❌ Error: {csv_path} not found. Run signal tracker first.")
        return

    df = pd.read_csv(csv_path)
    if df.empty:
        print("⚠️ Signal history is empty.")
        return

    print(f"📊 Analyzing {len(df)} logged breakout signals...\n")

    results = []

    for idx, row in df.iterrows():
        ticker = row.get("Ticker")
        signal_date_str = str(row.get("Date"))
        entry_price = float(row.get("Price", 0))

        if not ticker or entry_price <= 0:
            continue

        try:
            signal_date = datetime.strptime(signal_date_str, "%Y-%m-%d")
        except ValueError:
            continue

        # Fetch market data from signal date to current date + buffer
        start_date = signal_date.strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        history = yf.Ticker(ticker).history(start=start_date, end=end_date)

        if len(history) <= 1:
            # Not enough forward trading days yet
            continue

        # Extract forward closing prices
        t1_price = history["Close"].iloc[1] if len(history) > 1 else None
        t3_price = history["Close"].iloc[3] if len(history) > 3 else None
        t5_price = history["Close"].iloc[5] if len(history) > 5 else None

        # Calculate Returns (%)
        t1_roi = ((t1_price - entry_price) / entry_price * 100) if t1_price else None
        t3_roi = ((t3_price - entry_price) / entry_price * 100) if t3_price else None
        t5_roi = ((t5_price - entry_price) / entry_price * 100) if t5_price else None

        results.append({
            "Ticker": ticker,
            "Date": signal_date_str,
            "Entry Price": entry_price,
            "Score": row.get("Score", "N/A"),
            "T+1 ROI (%)": round(t1_roi, 2) if t1_roi is not None else "Pending",
            "T+3 ROI (%)": round(t3_roi, 2) if t3_roi is not None else "Pending",
            "T+5 ROI (%)": round(t5_roi, 2) if t5_roi is not None else "Pending",
        })

    report_df = pd.DataFrame(results)

    if report_df.empty:
        print("⏳ Waiting for more market trading days to resolve T+1/T+3/T+5 outcomes.")
        return

    # Filter completed trades for win rate calculation
    valid_t1 = report_df[report_df["T+1 ROI (%)"] != "Pending"]
    if not valid_t1.empty:
        win_count = len(valid_t1[valid_t1["T+1 ROI (%)"] > 0])
        total_count = len(valid_t1)
        win_rate = (win_count / total_count) * 100
        avg_roi = valid_t1["T+1 ROI (%)"].mean()

        print("=== 🏆 PERFORMANCE SUMMARY ===")
        print(f"Total Evaluated Signals : {total_count}")
        print(f"T+1 Win Rate            : {win_rate:.1f}%")
        print(f"T+1 Average Return      : {avg_roi:+.2f}%\n")

    print("=== 📋 DETAILED SIGNAL TRACK RECORD ===")
    print(report_df.to_string(index=False))

if __name__ == "__main__":
    run_performance_analytics()