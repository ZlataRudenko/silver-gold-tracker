from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.services.pricing import get_data

router = APIRouter()

@router.get("/api/prices")
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
