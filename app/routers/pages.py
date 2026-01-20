from datetime import datetime
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, Response, RedirectResponse

from app.core.settings import SUPPORTED_LANGS, COOKIE_LANG
from app.core.render import render_tmpl
from app.services.pricing import get_data, format_updated, compute_estimate
from app.services.storage import load_listings, read_jsonl, append_jsonl
from app.services.ids import get_or_set_user_id
from app.services.threads import (
    find_listing,
    find_thread,
    find_existing_thread,
    create_thread,
    read_messages,
    add_message,
)
from app.core.settings import THREADS_FILE

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
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


@router.get("/calculator", response_class=HTMLResponse)
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


@router.post("/calculator", response_class=HTMLResponse)
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
        if metal not in ("silver", "gold"):
            base_ctx["metal"] = "silver"
        if unit not in ("g", "kg", "oz", "don"):
            base_ctx["unit"] = "g"

    return render_tmpl(request, "calculator.html", base_ctx)


@router.get("/inbox", response_class=HTMLResponse)
def inbox(request: Request):
    ctx = {
        "request": request,
        "title": "Inbox",
        "page_title": "Inbox",
        "active_page": "inbox",
    }
    return render_tmpl(request, "inbox.html", ctx)


@router.get("/quote", response_class=HTMLResponse)
def quote(request: Request):
    ctx = {
        "request": request,
        "title": "Quick Quote",
        "page_title": "Quick Quote",
        "active_page": "quote",
    }
    return render_tmpl(request, "quote.html", ctx)


@router.get("/marketplace", response_class=HTMLResponse)
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


@router.get("/listing/{listing_id}", response_class=HTMLResponse)
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


@router.post("/listing/{listing_id}/contact")
def contact_listing(request: Request, listing_id: str):
    listing = find_listing(listing_id)
    if not listing:
        return HTMLResponse("Listing not found", status_code=404)

    resp = RedirectResponse(url="/", status_code=302)
    user_uid = get_or_set_user_id(request, resp)

    if user_uid == listing.get("owner_uid"):
        return HTMLResponse("You cannot contact your own listing.", status_code=400)

    threads = read_jsonl(THREADS_FILE)
    for t in threads:
        if t.get("listing_id") == listing_id and user_uid in t.get("participants", []):
            resp.headers["Location"] = f"/thread/{t['thread_id']}"
            return resp

    thread = create_thread(listing, user_uid)
    resp.headers["Location"] = f"/thread/{thread['thread_id']}"
    return resp


@router.get("/thread/{thread_id}", response_class=HTMLResponse)
def thread_page(request: Request, thread_id: str):
    thread = find_thread(thread_id)
    if not thread:
        return HTMLResponse("Thread not found", status_code=404)

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


@router.post("/thread/{thread_id}/send")
def send_message(
    request: Request,
    thread_id: str,
    text: str = Form(...),
):
    thread = find_thread(thread_id)

    # compat: if old thread record exists without participants
    if thread and "participants" not in thread:
        owner = thread.get("listing_owner_uid")
        buyer = thread.get("buyer_uid")
        if owner and buyer:
            thread["participants"] = [buyer, owner]

    if not thread:
        return HTMLResponse("Thread not found", status_code=404)

    resp = RedirectResponse(url=f"/thread/{thread_id}", status_code=302)
    user_uid = get_or_set_user_id(request, resp)
    if user_uid not in thread["participants"]:
        return HTMLResponse("Access denied", status_code=403)

    msg = {
        "sender_uid": user_uid,
        "sender_alias": "You",
        "text": text.strip(),
        "created_at": datetime.utcnow().isoformat(),
    }
    add_message(thread_id, msg)
    return resp


@router.get("/set-lang/{lang}", name="set_lang")
def set_lang(lang: str, request: Request):
    lang = (lang or "").strip().lower()
    if lang not in SUPPORTED_LANGS:
        lang = "en"

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
