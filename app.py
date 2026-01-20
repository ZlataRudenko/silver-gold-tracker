from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import requests
import time
import json
from pathlib import Path
from datetime import datetime
import uuid
from fastapi import Response
from fastapi.responses import RedirectResponse
import os
import threading

# ===== SETTINGS =====

COOKIE_USER = "anon_user_id"

# ---- i18n (language) ----
COOKIE_LANG = "lang"
SUPPORTED_LANGS = ("en", "ko")
DEFAULT_LANG = "en"


CACHE_TTL = 15 * 60    # 15 minutes
OZ_TO_GRAM = 31.1035
DON_TO_GRAM = 3.75


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INQUIRIES_FILE = DATA_DIR / "inquiries.jsonl"   # JSON Lines: 1 inquiry = 1 JSON per line
SELL_REQUESTS_FILE = DATA_DIR / "sell_requests.jsonl"  # sell requests (sellers)

SILVER_URL = "https://api.gold-api.com/price/XAG"          # XAG (silver) in USD per ounce
GOLD_URL = "https://api.gold-api.com/price/XAU"            # XAU (gold) in USD per ounce
FX_URL = "https://open.er-api.com/v6/latest/USD"           # USD -> KRW

LISTINGS_FILE = DATA_DIR / "listings.jsonl"
THREADS_FILE = DATA_DIR / "threads.jsonl"
MESSAGES_DIR = DATA_DIR / "messages"

# ===== APP =====
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

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


# ===== DATA FETCH =====
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
        # Do NOT update "updated" so the app will try again soon.
        print("ERROR in refresh_data:", repr(e))


def get_data():
    need_refresh = (
        cache["silver"] is None
        or cache["gold"] is None
        or cache["usdkrw"] is None
        or (time.time() - cache["updated"] > CACHE_TTL)
    )

    if need_refresh:
        refresh_data_async()   # <-- ВАЖНО: не refresh_data()

    return cache


def format_updated(ts: float) -> str:
    if not ts:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def compute_estimate(metal: str, unit: str, amount: float, data: dict):
    """
    Returns: grams, price_per_gram, estimate_total

    price_per_gram is KRW per gram based on live reference prices (no margin).
    estimate_total is calculated using reference price only.
    """
    if metal not in ("silver", "gold"):
        metal = "silver"

    if unit not in ("g", "kg", "oz", "don"):
        unit = "g"

    if amount is None or amount <= 0:
        raise ValueError("Amount must be greater than 0.")

    if data["silver"] is None or data["gold"] is None or data["usdkrw"] is None:
        raise ValueError("Prices are unavailable right now. Please try again.")

    # Reference price per gram (no margin)
    price_per_gram = data["silver"] if metal == "silver" else data["gold"]

    if unit == "kg":
        grams = amount * 1000.0
    elif unit == "oz":
        grams = amount * OZ_TO_GRAM
    elif unit == "don":
        grams = amount * DON_TO_GRAM
    else:
        grams = amount

    estimate_total = round(price_per_gram * grams, 2)

    return grams, price_per_gram, estimate_total


def ensure_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MESSAGES_DIR.mkdir(parents=True, exist_ok=True)

    for p in (LISTINGS_FILE, THREADS_FILE, INQUIRIES_FILE, SELL_REQUESTS_FILE):
        if not p.exists():
            p.write_text("", encoding="utf-8")

def get_or_set_user_id(request: Request, response: Response) -> str:
    uid = request.cookies.get(COOKIE_USER)
    if uid:
        return uid
    uid = str(uuid.uuid4())
    response.set_cookie(
        key=COOKIE_USER,
        value=uid,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 365,
    )
    return uid

def detect_lang(request: Request) -> str:
    """
    Priority:
    1) ?lang=en|ko
    2) cookie "lang"
    3) Accept-Language header (rough)
    4) DEFAULT_LANG
    """
    # 1) query
    q = (request.query_params.get("lang") or "").strip().lower()
    if q in SUPPORTED_LANGS:
        return q

    # 2) cookie
    c = (request.cookies.get(COOKIE_LANG) or "").strip().lower()
    if c in SUPPORTED_LANGS:
        return c

    # 3) Accept-Language (very simple)
    al = (request.headers.get("accept-language") or "").lower()
    if al.startswith("ko") or "ko-" in al:
        return "ko"

    return DEFAULT_LANG

I18N = {
    "en": {
        # navigation
        "nav.prices": "Prices",
        "nav.calculator": "Calculator",
        "nav.quote": "Quick Quote",
        "nav.marketplace": "Marketplace",
        "nav.inbox": "Inbox",
        "nav.request": "Leave a request",
        "lang.en": "EN",
        "lang.ko": "KO",
        "side.buy": "BUY",
        "side.sell": "SELL",


        # common
        "common.live": "Live",
        "common.live_prices": "Live prices",
        "common.live_estimate": "Live estimate",
        "common.in_development": "In development",
        "common.open": "Open",
        "common.posted": "Posted",
        "common.purity": "Purity",
        "common.alias": "Alias",
        "common.location": "Location",
        "common.updated": "Updated",
        "common.timestamp": "Timestamp",
        "common.used_price": "Used price",
        "common.estimated_total": "Estimated total",
        "common.reference_estimated_total": "Reference estimated total",

        # metals / units
        "metal.label": "Metal",
        "metal.silver": "Silver",
        "metal.gold": "Gold",
        "unit.label": "Unit",
        "unit.g": "grams",
        "unit.kg": "kilograms",
        "unit.oz": "ounces",
        "unit.don": "don (3.75 g)",
        "page.request.section_title_sell": "SALE DETAILS",
        "page.request.section_title_buy": "BUY DETAILS",

        "product.bar": "Bar",
        "product.coin": "Coin",
        "product.jewelry": "Jewelry",
        "product.other": "Other",


        # actions / buttons
        "btn.post_request": "Post request",
        "btn.generate": "Generate",
        "btn.copy": "Copy",
        "btn.preview_estimate": "Preview estimate",
        "btn.confirm_send": "Confirm & Send",
        "btn.confirm_publish": "Confirm & Publish",
        "btn.send": "Send",
        "page.request.buy_tab": "Buy",
        "page.request.sell_tab": "Sell",

        # forms
        "form.name": "Name",
        "form.contact": "Contact (Email / Phone / Telegram)",
        "form.product_type": "Product type",
        "form.purity_hint": "Purity (e.g. 999, 925, 750, unknown)",
        "form.amount": "Amount",
        "form.location_hint": "Location (city / country)",
        "form.message_optional": "Message (optional)",
        "form.type_message": "Type your message...",

        # pages
        "page.marketplace.subtitle": "Anonymous buy/sell requests. No contacts are shown publicly.",
        "page.marketplace.empty": "No active requests yet.",
        "page.request.details_buy": "Request details",
        "page.request.details_sell": "Sale details",
        "page.request.store_price_ts": "We store price + timestamp",
        "page.prices.title": "Silver & Gold Prices",
        "page.prices.subtitle": "Prices shown are final selling prices",
        "page.prices.krw_per_gram": "KRW per gram",
        "page.prices.auto_refresh": "Auto-refresh: 15 minutes",
        "page.marketplace.subtitle": "Anonymous buy/sell requests. No contacts are shown publicly.",
        "page.marketplace.empty": "No active requests yet.",
        "page.prices.title": "Silver & Gold Prices",
        "page.prices.subtitle": "Prices shown are final selling prices",
        "page.prices.krw_per_gram": "KRW per gram",
        "page.prices.auto_refresh": "Auto-refresh: 15 minutes",
        "page.request.buy_title": "Buy Request",
        "page.request.sell_title": "Sell Request",
        "page.request.footer_store_estimate": "We store estimate details to handle callbacks and confirmations.",
        "page.request.footer_autoprices": "Auto-prices via",
        "page.request.verify_note": "Please verify the estimate before sending. Prices may change with market updates.",
        "page.request.subtitle": "Send details and get an estimated reference total based on current prices.",
        "page.listing.title": "Listing",
        "page.listing.subtitle": "Details of the request.",
        "page.listing.message_label": "Message:",
        "btn.back": "Back",
        "btn.contact": "Contact",


    },

    "ko": {
        # navigation
        "nav.prices": "시세",
        "nav.calculator": "계산기",
        "nav.quote": "빠른 견적",
        "nav.marketplace": "거래 게시판",
        "nav.inbox": "메시지",
        "nav.request": "요청 등록",
        "lang.en": "EN",
        "lang.ko": "KO",
        "side.buy": "매수",
        "side.sell": "매도",


        # common
        "common.live": "실시간",
        "common.live_prices": "실시간 시세",
        "common.live_estimate": "실시간 견적",
        "common.in_development": "개발 중",
        "common.open": "열기",
        "common.posted": "등록됨",
        "common.purity": "순도",
        "common.alias": "별칭",
        "common.location": "지역",
        "common.updated": "업데이트",
        "common.timestamp": "기록 시간",
        "common.used_price": "적용 단가",
        "common.estimated_total": "예상 합계",
        "common.reference_estimated_total": "기준 예상 합계",

        # metals / units
        "metal.label": "금속",
        "metal.silver": "은",
        "metal.gold": "금",
        "unit.label": "단위",
        "unit.g": "그램",
        "unit.kg": "킬로그램",
        "unit.oz": "온스",
        "unit.don": "돈",
        "page.request.section_title_sell": "매도 정보",
        "page.request.section_title_buy": "매수 정보",

        "product.bar": "바",
        "product.coin": "코인",
        "product.jewelry": "주얼리",
        "product.other": "기타",


        # actions / buttons
        "btn.post_request": "요청 등록",
        "btn.generate": "생성",
        "btn.copy": "복사",
        "btn.preview_estimate": "견적 미리보기",
        "btn.confirm_send": "확인 후 전송",
        "btn.confirm_publish": "확인 후 등록",
        "btn.send": "보내기",
        "page.request.buy_tab": "매수",
        "page.request.sell_tab": "매도",


        # forms
        "form.name": "이름",
        "form.contact": "연락처 (이메일/전화/텔레그램)",
        "form.product_type": "제품 유형",
        "form.purity_hint": "순도 (예: 999, 925, 750, 미상)",
        "form.amount": "수량",
        "form.location_hint": "지역 (도시/국가)",
        "form.message_optional": "메시지 (선택)",
        "form.type_message": "메시지를 입력하세요...",

        # pages
        "page.marketplace.subtitle": "익명 매수/매도 요청입니다. 연락처는 공개되지 않습니다.",
        "page.marketplace.empty": "등록된 요청이 아직 없습니다.",
        "page.prices.title": "은 / 금 시세",
        "page.prices.subtitle": "표시된 가격은 최종 판매 기준입니다",
        "page.prices.krw_per_gram": "그램당 KRW",
        "page.prices.auto_refresh": "자동 새로고침: 15분",
        "page.marketplace.subtitle": "익명 매수/매도 요청입니다. 연락처는 공개되지 않습니다.",
        "page.marketplace.empty": "등록된 요청이 아직 없습니다.",
        "page.prices.title": "은/금 시세",
        "page.prices.subtitle": "표시된 가격은 최종 판매 기준입니다",
        "page.prices.krw_per_gram": "그램당 KRW",
        "page.prices.auto_refresh": "자동 새로고침: 15분",
        "page.request.buy_title": "매수 요청",
        "page.request.details_buy": "요청 정보",
        "page.request.details_sell": "매도 정보",
        "page.request.store_price_ts": "단가 및 시간 저장",
        "page.request.sell_title": "매도 요청",
        "page.request.footer_store_estimate": "콜백/확인을 위해 견적 정보를 저장합니다.",
        "page.request.footer_autoprices": "자동 시세:",
        "page.request.verify_note": "전송 전 견적을 확인하세요. 시세 업데이트로 가격이 변동될 수 있습니다.",
        "page.request.subtitle": "정보를 입력하면 현재 시세 기준 예상 합계를 계산해드립니다.",
        "page.listing.title": "요청 상세",
        "page.listing.subtitle": "요청 내용을 확인하세요.",
        "page.listing.message_label": "메시지:",
        "btn.back": "뒤로",
        "btn.contact": "연락하기",

    },
}

def t(lang: str, key: str) -> str:
    # fallback: ko -> en -> key
    return I18N.get(lang, I18N["en"]).get(key, I18N["en"].get(key, key))

def inject_i18n(ctx: dict, request: Request):
    lang = detect_lang(request)
    ctx["lang"] = lang
    ctx["t"] = lambda key: t(lang, key)
    return lang

def render_tmpl(request: Request, template_name: str, ctx: dict):
    """TemplateResponse with injected i18n (lang + t())."""
    inject_i18n(ctx, request)
    return templates.TemplateResponse(template_name, ctx)


def read_jsonl(path: Path):
    if not path.exists():
        return []
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except:
                pass
    return items

def append_jsonl(path: Path, obj: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        
def save_listing(listing: dict):
    ensure_storage()
    append_jsonl(LISTINGS_FILE, listing)

def load_listings():
    ensure_storage()
    return read_jsonl(LISTINGS_FILE)
       

def update_jsonl_by_id(path: Path, item_id: str, updates: dict, id_field="id"):
    items = read_jsonl(path)
    changed = False
    for x in items:
        if x.get(id_field) == item_id:
            x.update(updates)
            changed = True
            break
    if changed:
        with path.open("w", encoding="utf-8") as f:
            for x in items:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    return changed

def gen_alias(kind: str) -> str:
    # kind = "buy" or "sell"
    code = str(uuid.uuid4())[:4].upper()
    return ("Buyer" if kind == "buy" else "Seller") + f" #{code}"

def find_listing(listing_id: str):
    for x in read_jsonl(LISTINGS_FILE):
        if x.get("id") == listing_id:
            return x
    return None

@app.post("/listing/{listing_id}/contact")
def contact_listing(
    request: Request,
    response: Response,
    listing_id: str,
):
    listing = find_listing(listing_id)
    if not listing:
        return HTMLResponse("Listing not found", status_code=404)

# ✅ создаём ответ, который реально вернём браузеру
    resp = RedirectResponse(url="/", status_code=302)

# ✅ cookie ставим на resp (а не на response)
    user_uid = get_or_set_user_id(request, resp)

    # нельзя писать самому себе
    if user_uid == listing.get("owner_uid"):
        return HTMLResponse("You cannot contact your own listing.", status_code=400)

    # проверяем, есть ли уже thread
    threads = read_jsonl(THREADS_FILE)
    for t in threads:
        if t["listing_id"] == listing_id and user_uid in t["participants"]:
           resp.headers["Location"] = f"/thread/{t['thread_id']}"
           return resp

    # создаём новый thread
    thread_id = str(uuid.uuid4())

    thread = {
       "thread_id": thread_id,
       "listing_id": listing_id,
       "participants": [
           user_uid,                # 👈 тот, кто нажал Contact
           listing["owner_uid"],    # 👈 владелец заявки
        ],
        "created_at": datetime.utcnow().isoformat()
    }

    append_jsonl(THREADS_FILE, thread)

    resp.headers["Location"] = f"/thread/{thread_id}"
    return resp

def find_thread(thread_id: str):
    for t in read_jsonl(THREADS_FILE):
        if t.get("thread_id") == thread_id:
            return t
    return None

def save_thread(thread: dict):
    ensure_storage()
    append_jsonl(THREADS_FILE, thread)

def create_thread(listing: dict, buyer_uid: str) -> dict:
    thread_id = str(uuid.uuid4())
    owner_uid = listing.get("owner_uid")

    thread = {
        "thread_id": thread_id,
        "listing_id": listing["id"],

        # ✅ главный механизм доступа
        "participants": [buyer_uid, owner_uid],

        # (можно оставить для отладки/логов, но не обязательно)
        "listing_owner_uid": owner_uid,
        "buyer_uid": buyer_uid,

        "created_at": datetime.utcnow().isoformat(),
        "status": "open",
    }
    save_thread(thread)
    return thread


def find_existing_thread(listing_id: str, buyer_uid: str):
    for t in read_jsonl(THREADS_FILE):
        if t.get("listing_id") != listing_id:
          continue

# ✅ новый формат
    parts = t.get("participants")
    if isinstance(parts, list) and buyer_uid in parts:
      return t

# ✅ старый формат (на всякий случай, чтобы не сломать старые записи)
    if t.get("buyer_uid") == buyer_uid:
        return t
    return None


def thread_messages_path(thread_id: str) -> Path:
    return MESSAGES_DIR / f"{thread_id}.jsonl"

def read_messages(thread_id: str):
    return read_jsonl(thread_messages_path(thread_id))

def add_message(thread_id: str, msg: dict):
    append_jsonl(thread_messages_path(thread_id), msg)

@app.post("/thread/{thread_id}/send")
def send_message(
    request: Request,
    response: Response,
    thread_id: str,
    text: str = Form(...),
):
    thread = find_thread(thread_id)

    owner = None
    buyer = None
    if thread and "participants" not in thread:
       owner = thread.get("listing_owner_uid")
       buyer = thread.get("buyer_uid")
       if owner and buyer:
           thread["participants"] = [buyer, owner]


    if not thread:
        return HTMLResponse("Thread not found", status_code=404)

    user_uid = get_or_set_user_id(request, response)
    if user_uid not in thread["participants"]:
        return HTMLResponse("Access denied", status_code=403)

    alias = "You"
    msg = {
        "sender_uid": user_uid,
        "sender_alias": alias,
        "text": text.strip(),
        "created_at": datetime.utcnow().isoformat(),
    }

    add_message(thread_id, msg)

    return Response(
        status_code=302,
        headers={"Location": f"/thread/{thread_id}"},
    )

def render_inquiry(
    request: Request,
    *,
    metal: str = "silver",
    unit: str = "g",
    amount=None,
    product_type: str = "bar",
    purity: str = "",
    name: str = "",
    contact: str = "",
    location: str = "",
    message: str = "",
    estimate=None,
    price_per_gram=None,
    usdkrw=None,
    used_at=None,
    inquiry_id=None,
    success: bool = False,
    error=None,
):
    ctx = {
        "request": request,
        "title": "Inquiry",
        "active_page": "inquiry",
        "page_title": "Inquiry",

        "metal": metal,
        "unit": unit,
        "amount": amount,

        "product_type": product_type,
        "purity": purity,
        "name": name,
        "contact": contact,
        "location": location,
        "message": message,

        "estimate": estimate,
        "price_per_gram": price_per_gram,
        "usdkrw": usdkrw,
        "used_at": used_at,
        "inquiry_id": inquiry_id,

        "success": success,
        "error": error,
    }
    return render_tmpl(request, "inquiry.html", ctx)


def render_sell(
    request: Request,
    *,
    metal: str = "silver",
    unit: str = "g",
    amount=None,
    product_type: str = "bar",
    purity: str = "",
    name: str = "",
    contact: str = "",
    location: str = "",
    message: str = "",
    estimate=None,
    price_per_gram=None,
    usdkrw=None,
    used_at=None,
    inquiry_id=None,
    success: bool = False,
    error=None,
):
    ctx = {
        "request": request,
        "title": "Sell Request",
        "active_page": "sell",
        "page_title": "Sell Request",

        "metal": metal,
        "unit": unit,
        "amount": amount,

        "product_type": product_type,
        "purity": purity,
        "name": name,
        "contact": contact,
        "location": location,
        "message": message,

        "estimate": estimate,
        "price_per_gram": price_per_gram,
        "usdkrw": usdkrw,
        "used_at": used_at,
        "inquiry_id": inquiry_id,

        "success": success,
        "error": error,
    }
    return render_tmpl(request, "sell.html", ctx)
    
def render_request(
    request: Request,
    *,
    side: str = "sell",
    metal: str = "silver",
    unit: str = "g",
    amount=None,
    product_type: str = "bar",
    purity: str = "",
    name: str = "",
    contact: str = "",
    location: str = "",
    message: str = "",
    estimate=None,
    price_per_gram=None,
    usdkrw=None,
    used_at=None,
    request_id=None,
    lang: str = "en",
    success: bool = False,
    error=None,
):
    # нормализуем side
    side = (side or "sell").strip().lower()
    if side not in ("buy", "sell"):
        side = "sell"

    ctx = {
        "request": request,

        "title": "Request",
        "active_page": "request",
        "page_title": "Leave a request",

        "side": side,

        "metal": metal,
        "unit": unit,
        "amount": amount,

        "product_type": product_type,
        "purity": purity,
        "name": name,
        "contact": contact,
        "location": location,
        "message": message,

        "estimate": estimate,
        "price_per_gram": price_per_gram,
        "usdkrw": usdkrw,
        "used_at": used_at,
        "request_id": request_id,

        "success": success,
        "error": error,
    }

    return render_tmpl(request, "request.html", ctx)


@app.on_event("startup")
def on_startup():
    ensure_storage()
    refresh_data_async()

# ===== WEB PAGES =====

@app.get("/thread/{thread_id}", response_class=HTMLResponse)
def thread_page(request: Request, thread_id: str):
    thread = find_thread(thread_id)
    if not thread:
        return HTMLResponse("Thread not found", status_code=404)

    # ✅ создаём страницу-ответ
    messages = read_messages(thread_id)
    listing = find_listing(thread["listing_id"])

    ctx = {
        "request": request,
        "thread": thread,
        "listing": listing,
        "messages": messages,
    }
    page = render_tmpl(request, "thread.html", ctx)

    user_uid = get_or_set_user_id(request, page)
    if user_uid not in thread.get("participants", []):
        return HTMLResponse("Access denied", status_code=403)

    return page


@app.get("/marketplace", response_class=HTMLResponse)
def marketplace(request: Request):
    listings = load_listings()
    listings = sorted(listings, key=lambda x: x.get("created_at", ""), reverse=True)

    ctx = {
        "request": request,
        "title": "Marketplace",
        "page_title": "Marketplace",
        "active_page": "marketplace",
        "listings": listings,
    }
    return render_tmpl(request, "marketplace.html", ctx)

@app.get("/listing/{listing_id}", response_class=HTMLResponse)
def listing_page(request: Request, listing_id: str):
    listing = find_listing(listing_id)

    if not listing:
        ctx = {
            "request": request,
            "title": "Listing",
            "page_title": "Listing",
            "active_page": "marketplace",
            "listing": None,
            "error": "Listing not found.",
        }
        page = render_tmpl(request, "listing.html", ctx)
        page.status_code = 404
        return page

    ctx = {
        "request": request,
        "title": "Listing",
        "page_title": "Listing details",
        "active_page": "marketplace",
        "listing": listing,
        "error": None,
    }
    return render_tmpl(request, "listing.html", ctx)


# @app.post("/contact", response_class=HTMLResponse)
def contact_owner(
    request: Request,
    response: Response,
    listing_id: str = Form(...),
):
    uid = get_or_set_user_id(request, response)

    listing = find_listing(listing_id)
    if not listing:
        ctx = {
            "request": request,
            "title": "Listing",
            "page_title": "Listing details",
            "active_page": "marketplace",
            "listing": None,
            "error": "Listing not found.",
        }
        page = render_tmpl(request, "listing.html", ctx)
        page.status_code = 404
        return page

    # нельзя “контактировать саму себя”
    if listing.get("owner_uid") == uid:
        ctx = {
            "request": request,
            "title": "Listing",
            "page_title": "Listing details",
            "active_page": "marketplace",
            "listing": listing,
            "error": "You can’t contact your own listing.",
        }
        return render_tmpl(request, "listing.html", ctx)


    existing = find_existing_thread(listing_id, uid)
    if existing:
        thread_id = existing["thread_id"]
    else:
        thread = create_thread(listing, uid)
        thread_id = thread["thread_id"]

    # сразу отправляем в чат
    ctx = {
        "request": request,
        "title": "Redirect",
        "page_title": "Redirecting…",
        "active_page": "marketplace",
        "to": f"/thread/{thread_id}",
    }
    return render_tmpl(request, "redirect.html", ctx)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    data = get_data()

    error = None
    if data["silver"] is None or data["gold"] is None or data["usdkrw"] is None:
        error = "Price feed is temporarily unavailable. Please try again."

    ctx = {
        "request": request,
        "title": "Prices",
        "page_title": "Silver & Gold Prices",
        "active_page": "prices",
        "silver": round(data["silver"], 2) if data["silver"] is not None else None,
        "gold": round(data["gold"], 2) if data["gold"] is not None else None,
        "usdkrw": round(data["usdkrw"], 2) if data["usdkrw"] is not None else None,
        "updated": format_updated(data["updated"]),
        "error": error,
    }
    return render_tmpl(request, "index.html", ctx)


@app.get("/calculator", response_class=HTMLResponse)
def calculator(request: Request):
    ctx = {
        "request": request,
        "title": "Calculator",
        "page_title": "Precious Metals Calculator",
        "active_page": "calculator",
        "metal": "silver",
        "unit": "g",
        "amount": None,
        "margin_percent": 0,
        "result_ref": None,
        "result": None,
        "price_per_gram": None,
        "error": None,
    }
    return render_tmpl(request, "calculator.html", ctx)


@app.post("/calculator", response_class=HTMLResponse)
def calculator_result(
    request: Request,
    metal: str = Form("silver"),
    unit: str = Form("g"),
    amount: float = Form(...),
    margin_percent: float = Form(0),
):
    data = get_data()

    base_ctx = {
        "request": request,
        "title": "Calculator",
        "page_title": "Precious Metals Calculator",
        "active_page": "calculator",
        "metal": metal,
        "unit": unit,
        "amount": amount,
        "margin_percent": margin_percent,
        "result_ref": None,
        "result": None,
        "price_per_gram": None,
        "error": None,
    }

    try:
        grams, price_per_gram, total_ref = compute_estimate(metal, unit, amount, data)

        # validate margin
        if margin_percent is None:
           margin_percent = 0
        if margin_percent < 0 or margin_percent > 100:
           raise ValueError("Margin must be between 0 and 100.")

        total_final = round(total_ref * (1 + (margin_percent / 100.0)), 2)

        base_ctx["result_ref"] = total_ref
        base_ctx["result"] = total_final
        base_ctx["price_per_gram"] = round(price_per_gram, 2)
        base_ctx["margin_percent"] = margin_percent

    except Exception as e:
        base_ctx["error"] = str(e)
        # normalize inputs if user sent junk
        if metal not in ("silver", "gold"):
            base_ctx["metal"] = "silver"
        if unit not in ("g", "kg", "oz", "don"):
            base_ctx["unit"] = "g"
    return render_tmpl(request, "calculator.html", base_ctx)

@app.get("/inbox", response_class=HTMLResponse)
def inbox(request: Request):
    ctx = {
        "request": request,
        "title": "Inbox",
        "page_title": "Inbox",
        "active_page": "inbox",
    }
    return render_tmpl(request, "inbox.html", ctx)

@app.get("/quote", response_class=HTMLResponse)
def quote(request: Request):
    ctx = {
        "request": request,
        "title": "Quick Quote",
        "page_title": "Quick Quote",
        "active_page": "quote",
    }
    return render_tmpl(request, "quote.html", ctx)

@app.get("/request", response_class=HTMLResponse)
def request_page(request: Request, side: str = "sell"):
    # Язык НЕ трогаем здесь вообще.
    # Он берётся из cookie (которую ставит /set-lang/...)
    return render_request(request, side=side)

@app.get("/set-lang/{lang}", name="set_lang")
def set_lang(lang: str, request: Request):
    lang = (lang or "").strip().lower()
    if lang not in SUPPORTED_LANGS:
        lang = "en"

    # куда вернуться
    back = request.query_params.get("next") or "/"
    resp = RedirectResponse(url=back, status_code=302)

    resp.set_cookie(
        key=COOKIE_LANG,
        value=lang,
        httponly=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 365,
    )
    return resp


@app.post("/request/preview", response_class=HTMLResponse)
def request_preview(
    request: Request,
    side: str = Form("sell"),
    name: str = Form(""),
    contact: str = Form(""),
    metal: str = Form("silver"),
    product_type: str = Form("bar"),
    purity: str = Form(""),
    amount: float = Form(...),
    unit: str = Form("g"),
    location: str = Form(""),
    message: str = Form(""),
):
    side = (side or "sell").strip().lower()
    if side not in ("buy", "sell"):
        side = "sell"

    # clean
    name = (name or "").strip()
    contact = (contact or "").strip()
    purity = (purity or "").strip()
    location = (location or "").strip()
    message = (message or "").strip()
    product_type = (product_type or "bar").strip()

    data = get_data()

    try:
        grams, price_per_gram, estimate_total = compute_estimate(metal, unit, amount, data)
        used_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return render_request(
            request,
            side=side,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            estimate=estimate_total,
            price_per_gram=round(price_per_gram, 2),
            usdkrw=round(float(data["usdkrw"]), 2),
            used_at=used_at,
            inquiry_id=None,
            success=False,
            error=None,
        )
    except Exception as e:
        return render_request(
            request,
            side=side,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            estimate=None,
            price_per_gram=None,
            usdkrw=None,
            used_at=None,
            inquiry_id=None,
            success=False,
            error=str(e),
        )

@app.post("/request/confirm", response_class=HTMLResponse)
def request_confirm(
    request: Request,
    response: Response,
    side: str = Form("sell"),
    name: str = Form(...),
    contact: str = Form(...),
    metal: str = Form("silver"),
    product_type: str = Form("bar"),
    purity: str = Form(""),
    amount: float = Form(...),
    unit: str = Form("g"),
    location: str = Form(""),
    message: str = Form(""),
    confirm: str | None = Form(None),
):
    side = (side or "sell").strip().lower()
    if side not in ("buy", "sell"):
        side = "sell"

    # clean
    name = (name or "").strip()
    contact = (contact or "").strip()
    purity = (purity or "").strip()
    location = (location or "").strip()
    message = (message or "").strip()
    product_type = (product_type or "bar").strip()

    confirm_val = (confirm or "").strip().lower()
    if confirm_val not in ("1", "yes", "true", "ok"):
        return render_request(
            request,
            side=side,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            success=False,
            error="Please click Preview first, then Confirm.",
        )

    if not name or not contact:
        return render_request(
            request,
            side=side,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            success=False,
            error="Name and contact are required.",
        )

    data = get_data()

    try:
        grams, price_per_gram, estimate_total = compute_estimate(metal, unit, amount, data)
    except Exception as e:
        return render_request(
            request,
            side=side,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            success=False,
            error=str(e),
        )

    uid = get_or_set_user_id(request, response)

    # marketplace listing
    listing = {
        "id": str(uuid.uuid4()),
        "type": side,  # buy/sell
        "metal": metal,
        "product_type": product_type,
        "purity": purity,
        "amount": grams,
        "unit": "g",
        "price_per_gram": float(price_per_gram),
        "estimate_total": float(estimate_total),
        "location": location,
        "message": message,
        "created_at": datetime.utcnow().isoformat(),
        "owner_uid": uid,
        "alias": gen_alias(side),
        "contact_hidden": True,
    }
    save_listing(listing)

    now = datetime.now()
    used_at = now.strftime("%Y-%m-%d %H:%M:%S")
    req_id = str(uuid.uuid4())[:8]

    record = {
        "id": req_id,
        "created_at": now.isoformat(timespec="seconds"),
        "side": side,

        "metal": metal if metal in ("silver", "gold") else "silver",
        "product_type": product_type,
        "purity": purity,
        "amount": amount,
        "unit": unit if unit in ("g", "kg", "oz", "don") else "g",
        "grams": grams,

        "price_per_gram_used": round(float(price_per_gram), 6),
        "usdkrw_used": round(float(data["usdkrw"]), 6),
        "estimated_total_krw": estimate_total,

        "name": name,
        "contact": contact,
        "location": location,
        "message": message,
    }

    try:
        if side == "buy":
            append_jsonl(INQUIRIES_FILE, record)
        else:
            append_jsonl(SELL_REQUESTS_FILE, record)
    except Exception as e:
        print("ERROR saving request:", repr(e))

    return render_request(
        request,
        side=side,
        metal=metal,
        unit=unit,
        amount=amount,
        product_type=product_type,
        purity=purity,
        name=name,
        contact=contact,
        location=location,
        message=message,
        estimate=estimate_total,
        price_per_gram=round(price_per_gram, 2),
        usdkrw=round(float(data["usdkrw"]), 2),
        used_at=used_at,
        inquiry_id=req_id,  # чтобы шаблон мог показать ID
        success=True,
        error=None,
    )


@app.get("/inquiry", response_class=HTMLResponse)
def inquiry(request: Request):
    return RedirectResponse(url="/request?side=buy", status_code=302)


@app.post("/inquiry/preview", response_class=HTMLResponse)
def inquiry_preview(
    request: Request,
    name: str = Form(""),
    contact: str = Form(""),
    metal: str = Form("silver"),
    product_type: str = Form("bar"),
    purity: str = Form(""),
    amount: float = Form(...),
    unit: str = Form("g"),
    location: str = Form(""),
    message: str = Form(""),
):
    # clean strings
    name = (name or "").strip()
    contact = (contact or "").strip()
    purity = (purity or "").strip()
    location = (location or "").strip()
    message = (message or "").strip()
    product_type = (product_type or "bar").strip()

    data = get_data()

    try:
        grams, price_per_gram, estimate_total = compute_estimate(metal, unit, amount, data)
        used_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return render_inquiry(
            request,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            estimate=estimate_total,
            price_per_gram=round(price_per_gram, 2),
            usdkrw=round(float(data["usdkrw"]), 2),
            used_at=used_at,
            inquiry_id=None,
            success=False,
            error=None,
        )

    except Exception as e:
        return render_inquiry(
            request,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            estimate=None,
            price_per_gram=None,
            usdkrw=None,
            used_at=None,
            inquiry_id=None,
            success=False,
            error=str(e),
        )
        

@app.post("/inquiry", response_class=HTMLResponse)
def inquiry_submit(
    request: Request,
    response: Response,
    name: str = Form(...),
    contact: str = Form(...),
    metal: str = Form("silver"),
    product_type: str = Form("bar"),
    purity: str = Form(""),
    amount: float = Form(...),
    unit: str = Form("g"),
    location: str = Form(""),
    message: str = Form(""),
    # IMPORTANT: comma above is required when you add another param
    confirm: str | None = Form(None),
):
    # base validation + clean
    name = (name or "").strip()
    contact = (contact or "").strip()
    purity = (purity or "").strip()
    location = (location or "").strip()
    message = (message or "").strip()
    product_type = (product_type or "bar").strip()

    # enforce “preview -> confirm -> save” flow
    # (your template should send confirm="1" when user clicks the final button)
    confirm_val = (confirm or "").strip().lower()
    if confirm_val not in ("1", "yes", "true", "ok"):
        return render_inquiry(
            request,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            success=False,
            error="Please click Preview first, then Confirm to submit.",
        )

    if not name or not contact:
        return render_inquiry(
            request,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            success=False,
            error="Name and contact are required.",
        )

    data = get_data()

    try:
        grams, price_per_gram, estimate_total = compute_estimate(metal, unit, amount, data)
    except Exception as e:
        return render_inquiry(
            request,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            success=False,
            error=str(e),
        )
    
    uid = get_or_set_user_id(request, response)
    
    # --- create marketplace listing ---
    listing = {
        "id": str(uuid.uuid4()),
        "type": "buy",
        "metal": metal,
        "product_type": product_type,
        "purity": purity,
        "amount": grams,
        "unit": "g",
        "price_per_gram": float(price_per_gram),
        "estimate_total": float(estimate_total),
        "location": location,
        "message": message,
        "created_at": datetime.utcnow().isoformat(),

        "owner_uid": uid,
        "alias": gen_alias("buy"),

        "contact_hidden": True,
    }

    save_listing(listing)

    # timestamp + id
    now = datetime.now()
    used_at = now.strftime("%Y-%m-%d %H:%M:%S")
    inquiry_id = str(uuid.uuid4())[:8]

    record = {
        "id": inquiry_id,
        "created_at": now.isoformat(timespec="seconds"),
        "metal": metal if metal in ("silver", "gold") else "silver",
        "product_type": product_type,
        "purity": purity,
        "amount": amount,
        "unit": unit if unit in ("g", "kg", "oz", "don") else "g",
        "grams": grams,

        "price_per_gram_used": round(float(price_per_gram), 6),
        "usdkrw_used": round(float(data["usdkrw"]), 6),
        "estimated_total_krw": estimate_total,

        "name": name,
        "contact": contact,
        "location": location,
        "message": message,
    }

    # save (JSONL)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with INQUIRIES_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("ERROR saving inquiry:", repr(e))

    return render_inquiry(
        request,
        metal=metal,
        unit=unit,
        amount=amount,
        product_type=product_type,
        purity=purity,
        name=name,
        contact=contact,
        location=location,
        message=message,
        estimate=estimate_total,
        price_per_gram=round(price_per_gram, 2),
        usdkrw=round(float(data["usdkrw"]), 2),
        used_at=used_at,
        inquiry_id=inquiry_id,
        success=True,
        error=None,
    )

@app.get("/sell", response_class=HTMLResponse)
def sell(request: Request):
    return RedirectResponse(url="/request?side=sell", status_code=302)


@app.post("/sell/preview", response_class=HTMLResponse)
def sell_preview(
    request: Request,
    name: str = Form(""),
    contact: str = Form(""),
    metal: str = Form("silver"),
    product_type: str = Form("bar"),
    purity: str = Form(""),
    amount: float = Form(...),
    unit: str = Form("g"),
    location: str = Form(""),
    message: str = Form(""),
    side: str = Form("sell"),  # from template (optional)
):
    name = (name or "").strip()
    contact = (contact or "").strip()
    purity = (purity or "").strip()
    location = (location or "").strip()
    message = (message or "").strip()
    product_type = (product_type or "bar").strip()

    data = get_data()

    try:
        grams, price_per_gram, estimate_total = compute_estimate(metal, unit, amount, data)
        used_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return render_sell(
            request,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            estimate=estimate_total,
            price_per_gram=round(price_per_gram, 2),
            usdkrw=round(float(data["usdkrw"]), 2),
            used_at=used_at,
            inquiry_id=None,
            success=False,
            error=None,
        )

    except Exception as e:
        return render_sell(
            request,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            estimate=None,
            price_per_gram=None,
            usdkrw=None,
            used_at=None,
            inquiry_id=None,
            success=False,
            error=str(e),
        )


@app.post("/sell", response_class=HTMLResponse)
def sell_submit(
    request: Request,
    response: Response,
    name: str = Form(...),
    contact: str = Form(...),
    metal: str = Form("silver"),
    product_type: str = Form("bar"),
    purity: str = Form(""),
    amount: float = Form(...),
    unit: str = Form("g"),
    location: str = Form(""),
    message: str = Form(""),
    confirm: str | None = Form(None),
    side: str = Form("sell"),
):
    name = (name or "").strip()
    contact = (contact or "").strip()
    purity = (purity or "").strip()
    location = (location or "").strip()
    message = (message or "").strip()
    product_type = (product_type or "bar").strip()

    confirm_val = (confirm or "").strip().lower()
    if confirm_val not in ("1", "yes", "true", "ok"):
        return render_sell(
            request,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            success=False,
            error="Please click Preview first, then Confirm to publish.",
        )

    if not name or not contact:
        return render_sell(
            request,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            success=False,
            error="Name and contact are required.",
        )

    data = get_data()

    try:
        grams, price_per_gram, estimate_total = compute_estimate(metal, unit, amount, data)
    except Exception as e:
        return render_sell(
            request,
            metal=metal,
            unit=unit,
            amount=amount,
            product_type=product_type,
            purity=purity,
            name=name,
            contact=contact,
            location=location,
            message=message,
            success=False,
            error=str(e),
        )

    now = datetime.now()
    used_at = now.strftime("%Y-%m-%d %H:%M:%S")
    inquiry_id = str(uuid.uuid4())[:8]
    
    uid = get_or_set_user_id(request, response)

    listing = {
        "id": str(uuid.uuid4()),
        "type": "sell",
        "metal": metal,
        "product_type": product_type,
        "purity": purity,
        "amount": grams,
        "unit": "g",
        "price_per_gram": float(price_per_gram),
        "estimate_total": float(estimate_total),
        "location": location,
        "message": message,
        "created_at": datetime.utcnow().isoformat(),
        "owner_uid": uid,
        "alias": gen_alias("sell"),
        "contact_hidden": True,
    }
    save_listing(listing)

    record = {
        "id": inquiry_id,
        "created_at": now.isoformat(timespec="seconds"),
        "side": "sell",

        "metal": metal if metal in ("silver", "gold") else "silver",
        "product_type": product_type,
        "purity": purity,
        "amount": amount,
        "unit": unit if unit in ("g", "kg", "oz", "don") else "g",
        "grams": grams,

        "price_per_gram_used": round(float(price_per_gram), 6),
        "usdkrw_used": round(float(data["usdkrw"]), 6),
        "estimated_total_krw": estimate_total,

        "name": name,
        "contact": contact,
        "location": location,
        "message": message,
    }

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with SELL_REQUESTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("ERROR saving sell request:", repr(e))

    return render_sell(
        request,
        metal=metal,
        unit=unit,
        amount=amount,
        product_type=product_type,
        purity=purity,
        name=name,
        contact=contact,
        location=location,
        message=message,
        estimate=estimate_total,
        price_per_gram=round(price_per_gram, 2),
        usdkrw=round(float(data["usdkrw"]), 2),
        used_at=used_at,
        inquiry_id=inquiry_id,
        success=True,
        error=None,
    )


# ===== API =====
@app.get("/api/prices")
def api_prices():
    data = get_data()
    return JSONResponse(
        {
            "silver_krw_per_gram": round(data["silver"], 2) if data["silver"] is not None else None,
            "gold_krw_per_gram": round(data["gold"], 2) if data["gold"] is not None else None,
            "usdkrw": round(data["usdkrw"], 2) if data["usdkrw"] is not None else None,
            "margin_percent": 0,
            "updated": data["updated"],
        }
    )
