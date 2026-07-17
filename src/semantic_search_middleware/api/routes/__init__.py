from .chat import router as chat_router
from .health import router as health_router
from .search import router as search_router

__all__ = ["chat_router", "health_router", "search_router"]
