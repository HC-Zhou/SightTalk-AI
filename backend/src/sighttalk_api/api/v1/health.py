"""Health-check API route."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Return a lightweight liveness response."""
    return {"status": "ok", "service": "sighttalk-api"}
