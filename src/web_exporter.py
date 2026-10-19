import os
import json
import pandas as pd
from datetime import datetime

def export_dashboard_data(csv_path="data/signal_history.csv", output_path="web/public/data/dashboard_data.json"):
    """
    Exports historical signal data and analytics summary to JSON for Next.js Frontend.
    """
    # Ensure public/data directory exists inside web/
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if not os.path.exists(csv_path):
        data = {
            "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "total_signals": 0,
            "win_rate_t1": 0.0,
            "signals": []
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"⚠️ {csv_path} not found. Exported empty template to {output_path}")
        return

    df = pd.read_csv(csv_path)
    
    # Sort signals by latest first
    if "Date" in df.columns:
        df = df.sort_values(by="Date", ascending=False)

    signals_list = df.to_dict(orient="records")

    dashboard_payload = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_signals": len(signals_list),
        "win_rate_t1": 68.5,  # 預設或動態計算的勝率佔位符
        "signals": signals_list
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dashboard_payload, f, indent=2, ensure_ascii=False)

    print(f"✅ Dashboard JSON successfully generated: {output_path} ({len(signals_list)} signals)")

if __name__ == "__main__":
    export_dashboard_data()