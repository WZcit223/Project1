"""Run the UI alone against a running Application API: ``uv run python -m industrial_ai_ui``.

``IAI_UI_API_URL`` (default ``http://127.0.0.1:8000``) points at the API; ``IAI_UI_PORT`` (default
8001) is the UI port. For a single-process demo use ``scripts/serve.py`` instead.
"""

import os

import uvicorn

from industrial_ai_ui.app import create_ui_app
from industrial_ai_ui.client import ApiClient


def main() -> None:
    api = ApiClient.for_url(os.environ.get("IAI_UI_API_URL", "http://127.0.0.1:8000"))
    uvicorn.run(
        create_ui_app(api), host="127.0.0.1", port=int(os.environ.get("IAI_UI_PORT", "8001"))
    )


if __name__ == "__main__":
    main()
