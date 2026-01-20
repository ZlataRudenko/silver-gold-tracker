from fastapi import Request
from app.core.settings import SUPPORTED_LANGS, DEFAULT_LANG

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


def detect_lang(request: Request) -> str:
    """
    Priority:
    1) ?lang=en|ko
    2) cookie "lang"
    3) Accept-Language header (rough)
    4) DEFAULT_LANG
    """
    q = (request.query_params.get("lang") or "").strip().lower()
    if q in SUPPORTED_LANGS:
        return q

    c = (request.cookies.get("lang") or "").strip().lower()
    if c in SUPPORTED_LANGS:
        return c

    al = (request.headers.get("accept-language") or "").lower()
    if al.startswith("ko") or "ko-" in al:
        return "ko"

    return DEFAULT_LANG


def t(lang: str, key: str) -> str:
    # fallback: ko -> en -> key
    return I18N.get(lang, I18N["en"]).get(key, I18N["en"].get(key, key))


def inject_i18n(ctx: dict, request: Request) -> str:
    lang = detect_lang(request)
    ctx["lang"] = lang
    ctx["t"] = lambda key: t(lang, key)
    return lang
