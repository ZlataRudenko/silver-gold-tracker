from pathlib import Path

# ===== SETTINGS =====

COOKIE_USER = "anon_user_id"

# ---- i18n (language) ----
COOKIE_LANG = "lang"
SUPPORTED_LANGS = ("en", "ko")
DEFAULT_LANG = "en"

# ---- cache / units ----
CACHE_TTL = 15 * 60    # 15 minutes
OZ_TO_GRAM = 31.1035
DON_TO_GRAM = 3.75

# ---- paths ----
# project root (folder that contains /templates, /static, /data)
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
MESSAGES_DIR = DATA_DIR / "messages"

INQUIRIES_FILE = DATA_DIR / "inquiries.jsonl"          # buy requests (buyers)
SELL_REQUESTS_FILE = DATA_DIR / "sell_requests.jsonl"  # sell requests (sellers)

LISTINGS_FILE = DATA_DIR / "listings.jsonl"
THREADS_FILE = DATA_DIR / "threads.jsonl"

# ---- external data sources ----
SILVER_URL = "https://api.gold-api.com/price/XAG"      # XAG (silver) in USD per ounce
GOLD_URL = "https://api.gold-api.com/price/XAU"        # XAU (gold) in USD per ounce
FX_URL = "https://open.er-api.com/v6/latest/USD"       # USD -> KRW
