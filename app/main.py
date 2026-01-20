from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.settings import BASE_DIR
from app.services.storage import ensure_storage
from app.services.pricing import refresh_data_async

from app.routers.pages import router as pages_router
from app.routers.request_flow import router as request_router
from app.routers.api import router as api_router

app = FastAPI()

# static
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# routers
app.include_router(pages_router)
app.include_router(request_router)
app.include_router(api_router)

@app.on_event("startup")
def on_startup():
    ensure_storage()
    refresh_data_async()
