"""Shared router dependencies."""

from typing import Annotated

from fastapi import Depends, Request

from industrial_ai.application import ApplicationService


def get_service(request: Request) -> ApplicationService:
    """The app's application service, created on first use from the app's settings."""
    service: ApplicationService | None = getattr(request.app.state, "service", None)
    if service is None:
        service = ApplicationService(request.app.state.settings)
        request.app.state.service = service
    return service


Service = Annotated[ApplicationService, Depends(get_service)]
