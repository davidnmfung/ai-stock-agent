import os

# Telegram 設定
RAW_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_BOT_TOKEN = (
    RAW_BOT_TOKEN[3:] if RAW_BOT_TOKEN.startswith("bot") else RAW_BOT_TOKEN
)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# 外部 API Keys
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# 核心監控清單 (Core Watchlist)
CORE_WATCHLIST = [
    "SMCX", "AIOT", "SOUN", "BBAI", "RGTI", "QUBT", "CRML", "GRML", "GLND", "IONQ",
    "PLTR", "MARA", "RIOT", "CLSK", "SOFI", "UPST", "AFRM", "PATH", "ASTS", "RKLB",
    "JOBY", "LUNR", "OKLO", "SMR", "NBIS", "PPLI", "BIRK", "VECO", "FLY", "ABCL",
    "CAAP", "ALVO", "DFTX", "GAP", "AVPT", "AEO", "PACS", "WAY", "CCL", "MGNI"
]

# 量化篩選門檻
MIN_RVOL = 1.3
MIN_GAIN = 1.5
MIN_DOLLAR_VOL = 10_000_000
MIN_INTRADAY_LOC = 0.70
MIN_ATR_RATIO = 1.2