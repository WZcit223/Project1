"""Single-process demo server: Application API at ``/api`` and the UI at ``/ui``.

    uv run python scripts/serve.py        # then open http://127.0.0.1:8000/ui/

The UI still talks to the API through HTTP semantics (an in-process ASGI transport); it imports no
framework module. Settings come from the environment / ``.env`` (``IAI_*``).
"""

import httpx2
import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from industrial_ai.api.app import create_app
from industrial_ai.core.config import Settings, load_settings
from industrial_ai.core.logging import configure_logging
from industrial_ai_ui.app import create_ui_app
from industrial_ai_ui.client import ApiClient


def build_app(settings: Settings) -> FastAPI:
    """API app with the UI mounted at ``/ui``; the UI calls the API in-process over ASGI."""
    api = create_app(settings)
    transport = httpx2.ASGITransport(app=api)
    client = ApiClient(httpx2.AsyncClient(transport=transport, base_url="http://api", timeout=300))
    api.mount("/ui", create_ui_app(client))

    @api.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/ui/")

    return api


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    uvicorn.run(build_app(settings), host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()
