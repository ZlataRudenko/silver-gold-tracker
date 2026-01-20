import uuid
from fastapi import Request, Response
from app.core.settings import COOKIE_USER


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


def gen_alias(kind: str) -> str:
    # kind = "buy" or "sell"
    code = str(uuid.uuid4())[:4].upper()
    return ("Buyer" if kind == "buy" else "Seller") + f" #{code}"
