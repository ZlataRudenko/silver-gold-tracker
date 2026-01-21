import uuid
import json
from datetime import datetime
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.render import render_tmpl
from app.services.pricing import get_data, compute_estimate
from app.services.ids import get_or_set_user_id, gen_alias
from app.services.storage import append_jsonl, save_listing
from app.core.settings import INQUIRIES_FILE, SELL_REQUESTS_FILE, DATA_DIR

router = APIRouter()

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
    success: bool = False,
    error=None,
):
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


@router.get("/request", response_class=HTMLResponse)
def request_page(request: Request, side: str = "sell"):
    return render_request(request, side=side)


@router.post("/request/preview", response_class=HTMLResponse)
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
            request_id=None,
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
            request_id=None,
            success=False,
            error=str(e),
        )


@router.post("/request/confirm", response_class=HTMLResponse)
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
        request_id=req_id,
        success=True,
        error=None,
    )


# legacy redirects
@router.get("/inquiry", response_class=HTMLResponse)
def inquiry_redirect():
    return RedirectResponse(url="/request?side=buy", status_code=302)


@router.get("/sell", response_class=HTMLResponse)
def sell_redirect():
    return RedirectResponse(url="/request?side=sell", status_code=302)
