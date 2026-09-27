"""``GET /health`` — liveness check (docs/application-api.md §2)."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from industrial_ai import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report that the API process is up, with the framework version."""
    return HealthResponse(status="ok", version=__version__)
