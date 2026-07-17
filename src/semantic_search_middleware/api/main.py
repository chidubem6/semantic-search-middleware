from fastapi import FastAPI

from semantic_search_middleware.api.routes import chat_router, health_router, search_router
from semantic_search_middleware.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(health_router)
app.include_router(search_router, prefix=settings.api_prefix)
app.include_router(chat_router, prefix=settings.api_prefix)
