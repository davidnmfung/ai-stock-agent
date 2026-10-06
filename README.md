# 📈 Automated Quantitative Equity Scanner & Options Momentum Engine

An enterprise-grade, serverless quantitative trading engine designed to scan US equity markets for volume breakout setups, evaluate option chain liquidity, and automatically dispatch real-time institutional alerts.

Built with a modular Python architecture and deployed via GitHub Actions CI/CD pipeline, this system features an automated forward-testing logger to build verifiable track records for strategy backtesting.

---

## 🏗️ System Architecture & Data Flow

```mermaid
graph TD
    A[Cron Schedule / Market Open] -->|Trigger| B[GitHub Actions Runner]
    B --> C[Market Hours Evaluator]
    C -->|Market Open| D[Data Pipeline Engine]
    C -->|Market Closed| Z[Graceful Exit]
    
    D -->|Fetch OHLCV| E[yFinance API]
    D -->|Fetch News| F[Finnhub API]
    
    E --> G[Strategy Engine]
    G -->|RVOL ≥ 1.3x & Gain ≥ 1.5%| H[Breakout Filter]
    
    H --> I[Options Chain Analytics]
    I -->|Select Strike & Expiry| J[Risk/Reward Advisor]
    
    J --> K[Notifier Engine]
    K -->|Push Alert| L[Telegram VIP Channel]
    
    J --> M[Signal Tracker Engine]
    M -->|Append Entry| N[(data/signal_history.csv)]