# 🚀 AlphaPulse AI: Quantitative Momentum Scanner & Event Agent

> 🏆 **Recognition**: Architecture selected for the [XERJ Corpus Hub](https://github.com/xerj-org/xerj) as an exemplary open-source reference for production-grade modular software design.

An institutional-grade, automated quantitative equity scanner and event-driven catalyst interpreter. Designed for systematic momentum tracking in US equity markets using quantitative filters and generative AI (Gemini 1.5 Flash).

---

## 🌟 Key Features

- **Dual-Track Market Monitoring**:
  * **Core Watchlist Heartbeat**: Tracks custom high-momentum growth equities.
  * **Dynamic Market Gainers**: Real-time screening of top intraday gainers across US exchanges via yFinance API.
- **Algorithmic Signal Screening**:
  * Relative Volume (**RVOL >= 1.3x**) filtering to detect institutional order flow.
  * True Range / Volatility metrics utilizing **14-day ATR ratios**.
  * Intraday price location scoring to weed out late-day fading stocks.
- **Generative AI Catalyst Scoring**:
  * Integrates **Finnhub API** for real-time news aggregation.
  * Uses **Gemini 1.5 Flash** to score news catalysts (1.0 to 10.0 scale) and generate concise event summaries.
- **Persistent Forward Testing & Analytics**:
  * **`SignalTracker`**: Automatically logs daily breakout signals to `data/signal_history.csv` for win-rate backtesting and performance analytics.
- **Serverless CI/CD Delivery**:
  * Runs seamlessly on **GitHub Actions** with automated multi-chunk **Telegram Bot** alerts.

---

## 🏗️ Architecture & Modular Design

```text
ai-stock-agent/
├── .github/
│   └── workflows/
│       └── stock_scanner.yml     # Serverless CI/CD Scheduler
├── config/
│   └── settings.py               # Watchlists, Thresholds & API Configs
├── src/
│   ├── __init__.py
│   ├── data_engine.py            # Market & News Aggregator (yFinance/Finnhub)
│   ├── strategy_engine.py        # Gemini AI Sentiment & Event Catalyst Engine
│   ├── tracker.py                # Historical Signal & Win-Rate Tracker
│   ├── analytics.py              # Automated Win-Rate & Multi-Day ROI Backtesting Engine
│   └── notifier.py               # Multi-chunk Telegram Alert Pipeline
├── data/
│   └── signal_history.csv        # Persistent Storage for Forward Testing
├── main.py                       # Application Entry Point
└── requirements.txt