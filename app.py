from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import requests
import time

# ===== НАСТРОЙКИ =====
MARGIN = 0.25          # 25% profit margin
CACHE_TTL = 15 * 60    # 15 минут
OZ_TO_GRAM = 31.1035

SILVER_URL = "https://api.gold-api.com/price/XAG"
GOLD_URL = "https://api.gold-api.com/price/XAU"
FX_URL = "https://open.er-api.com/v6/latest/USD"

# ===== APP =====
app = FastAPI()
templates = Jinja2Templates(directory="templates")

cache = {
    "updated": 0,
    "silver": None,
    "gold": None,
    "usdkrw": None
}

# ===== DATA FETCH =====
def refresh_data():
    silver_usd = float(requests.get(SILVER_URL).json()["price"])
    gold_usd = float(requests.get(GOLD_URL).json()["price"])
    usdkrw = float(requests.get(FX_URL).json()["rates"]["KRW"])

    # базовая цена (без маржи)
    silver_base = (silver_usd * usdkrw) / OZ_TO_GRAM
    gold_base = (gold_usd * usdkrw) / OZ_TO_GRAM

    # цена с маржой
    cache["silver"] = silver_base * (1 + MARGIN)
    cache["gold"] = gold_base * (1 + MARGIN)
    cache["usdkrw"] = usdkrw
    cache["updated"] = time.time()

def get_data():
    if time.time() - cache["updated"] > CACHE_TTL:
        refresh_data()
    return cache

# ===== WEB PAGE =====
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    data = get_data()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "silver": round(data["silver"], 2),
        "gold": round(data["gold"], 2),
        "usdkrw": round(data["usdkrw"], 2),
        "margin": int(MARGIN * 100),
        "updated": time.strftime("%Y-%m-%d %H:%M:%S")
    })

# ===== API =====
@app.get("/api/prices")
def api_prices():
    data = get_data()
    return JSONResponse({
        "silver_krw_per_gram": round(data["silver"], 2),
        "gold_krw_per_gram": round(data["gold"], 2),
        "usdkrw": round(data["usdkrw"], 2),
        "margin_percent": int(MARGIN * 100),
        "updated": data["updated"]
    })
