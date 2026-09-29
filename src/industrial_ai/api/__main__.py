"""Run the Application API locally: ``uv run python -m industrial_ai.api``."""

import uvicorn

from industrial_ai.api.app import create_app
from industrial_ai.core.config import load_settings
from industrial_ai.core.logging import configure_logging


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        create_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.value.lower(),
    )


if __name__ == "__main__":
    main()
