import csv
from datetime import datetime
import os
import pytz


class SignalTracker:

  def __init__(self, filepath='data/signal_history.csv'):
    self.filepath = filepath
    self._ensure_file_exists()

  def _ensure_file_exists(self):
    os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
    if not os.path.exists(self.filepath):
      with open(self.filepath, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Timestamp_EDT',
            'Ticker',
            'Entry_Price',
            'Gain_Pct',
            'RVOL',
            'Sector',
            'Short_Float',
            'Status',
        ])

  def log_signals(self, signals: list):
    tz = pytz.timezone('US/Eastern')
    now_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

    with open(self.filepath, mode='a', newline='', encoding='utf-8') as f:
      writer = csv.writer(f)
      for sig in signals:
        writer.writerow([
            now_str,
            sig.get('ticker'),
            sig.get('price'),
            sig.get('gain_pct'),
            sig.get('rvol'),
            sig.get('sector', 'N/A'),
            sig.get('short_float', 'N/A'),
            'ACTIVE',
        ])
    print(f'📊 [Tracker] 已成功記錄 {len(signals)} 筆預警訊號至歷史庫。')