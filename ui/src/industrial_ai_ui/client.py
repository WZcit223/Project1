"""HTTP client for the Application API — the UI's only data source."""

from typing import Any

import httpx2


class ApiError(Exception):
    """An Application API error response (``{"error": {code, message, details}}``)."""

    def __init__(self, status: int, code: str, message: str, details: dict[str, Any]) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.details = details


class ApiClient:
    """Thin async wrapper: JSON in, JSON out, API errors raised as :class:`ApiError`."""

    def __init__(self, http: httpx2.AsyncClient) -> None:
        self._http = http

    @classmethod
    def for_url(cls, base_url: str, timeout: float = 300.0) -> "ApiClient":
        return cls(httpx2.AsyncClient(base_url=base_url, timeout=timeout))

    async def get(self, path: str, params: Any = None) -> Any:
        return self._json(await self._http.get(path, params=params))

    async def post(self, path: str, body: Any) -> Any:
        return self._json(await self._http.post(path, json=body))

    async def aclose(self) -> None:
        await self._http.aclose()

    @staticmethod
    def _json(response: httpx2.Response) -> Any:
        if response.is_success:
            return response.json()
        try:
            error = response.json()["error"]
        except (ValueError, KeyError, TypeError):
            raise ApiError(response.status_code, "HTTP_ERROR", response.text, {}) from None
        raise ApiError(
            response.status_code,
            str(error.get("code", "ERROR")),
            str(error.get("message", "")),
            dict(error.get("details") or {}),
        )
