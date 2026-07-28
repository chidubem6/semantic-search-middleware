"""Health-check route.

Exposes a simple ``/health`` endpoint returning an OK status for liveness
probes. Part of the API (driving) adapter.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
