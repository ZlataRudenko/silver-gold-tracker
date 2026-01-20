import time
import threading
import requests

from app.core.settings import (
    CACHE_TTL,
    OZ_TO_GRAM,
    DON_TO_GRAM,
    SILVER_URL,
    GOLD_URL,
    FX_URL,
)

cache = {
    "updated": 0.0,
    "silver": None,   # KRW per gram (reference)
    "gold": None,     # KRW per gram (reference)
    "usdkrw": None
}

_refresh_lock = threading.Lock()
_refresh_in_progress = False


def refresh_data_async():
    """Run refresh_data() in background so web pages never hang."""
    global _refresh_in_progress

    if _refresh_in_progress:
        return

    with _refresh_lock:
        if _refresh_in_progress:
            return
        _refresh_in_progress = True

    def _job():
        global _refresh_in_progress
        try:
            refresh_data()
        finally:
            _refresh_in_progress = False

    threading.Thread(target=_job, daemon=True).start()


def refresh_data():
    """Fetch external prices with timeouts.
    If external API fails, do NOT crash the server.
    """
    try:
        silver_json = requests.get(SILVER_URL, timeout=5).json()
        gold_json = requests.get(GOLD_URL, timeout=5).json()
        fx_json = requests.get(FX_URL, timeout=5).json()

        silver_usd_per_oz = float(silver_json["price"])
        gold_usd_per_oz = float(gold_json["price"])
        usdkrw = float(fx_json["rates"]["KRW"])

        # Convert: USD/oz -> KRW/gram
        silver_krw_per_gram = (silver_usd_per_oz * usdkrw) / OZ_TO_GRAM
        gold_krw_per_gram = (gold_usd_per_oz * usdkrw) / OZ_TO_GRAM

        cache["silver"] = silver_krw_per_gram
        cache["gold"] = gold_krw_per_gram
        cache["usdkrw"] = usdkrw
        cache["updated"] = time.time()

    except Exception as e:
        # Keep cache as-is, so pages still open even if API is down.
        print("ERROR in refresh_data:", repr(e))


def get_data():
    need_refresh = (
        cache["silver"] is None
        or cache["gold"] is None
        or cache["usdkrw"] is None
        or (time.time() - cache["updated"] > CACHE_TTL)
    )

    if need_refresh:
        refresh_data_async()   # IMPORTANT: do not block

    return cache


def format_updated(ts: float) -> str:
    if not ts:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def compute_estimate(metal: str, unit: str, amount: float, data: dict):
    """
    Returns: grams, price_per_gram, estimate_total
    price_per_gram is KRW per gram based on live reference prices (no margin).
    """
    if metal not in ("silver", "gold"):
        metal = "silver"

    if unit not in ("g", "kg", "oz", "don"):
        unit = "g"

    if amount is None or amount <= 0:
        raise ValueError("Amount must be greater than 0.")

    if data.get("silver") is None or data.get("gold") is None or data.get("usdkrw") is None:
        raise ValueError("Prices are unavailable right now. Please try again.")

    price_per_gram = data["silver"] if metal == "silver" else data["gold"]

    # Convert input amount -> grams
    if unit == "kg":
        grams = amount * 1000.0
    elif unit == "oz":
        grams = amount * OZ_TO_GRAM
    elif unit == "don":
        grams = amount * DON_TO_GRAM
    else:
        grams = amount

    # Total in KRW (reference)
    estimate_total = round(price_per_gram * grams, 2)
    return grams, price_per_gram, estimate_total
