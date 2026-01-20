from fastapi import Request
from fastapi.templating import Jinja2Templates
from app.core.settings import BASE_DIR
from app.core.i18n import inject_i18n

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def render_tmpl(request: Request, template_name: str, ctx: dict):
    """TemplateResponse with injected i18n (lang + t())."""
    inject_i18n(ctx, request)
    return templates.TemplateResponse(template_name, ctx)
