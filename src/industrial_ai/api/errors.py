"""Error responses: ``{"error": {"code", "message", "details"}}`` (docs/application-api.md §1)."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import JsonValue

from industrial_ai.core.errors import (
    ApplicationError,
    ConstraintViolationError,
    DatasetAlreadyRegisteredError,
    DatasetNotFoundError,
    DuplicatePluginError,
    GeneratorParameterError,
    IndustrialAIError,
    PluginNotFoundError,
    RunFailedError,
    RunNotFoundError,
    RunRequestError,
    ScenarioValidationError,
)

logger = logging.getLogger(__name__)

# Most specific first: the first matching class decides status and code.
ERROR_MAP: tuple[tuple[type[Exception], int, str], ...] = (
    (RunFailedError, 500, "RUN_FAILED"),
    (RunNotFoundError, 404, "RUN_NOT_FOUND"),
    (DatasetNotFoundError, 404, "DATASET_NOT_FOUND"),
    (PluginNotFoundError, 404, "NOT_FOUND"),
    (RunRequestError, 422, "INVALID_RUN_REQUEST"),
    (ScenarioValidationError, 422, "INVALID_SCENARIO"),
    (GeneratorParameterError, 422, "INVALID_GENERATION_REQUEST"),
    (ConstraintViolationError, 422, "CONSTRAINT_VIOLATION"),
    (DuplicatePluginError, 409, "CONFLICT"),
    (DatasetAlreadyRegisteredError, 409, "CONFLICT"),
    (ApplicationError, 400, "BAD_REQUEST"),
    (IndustrialAIError, 400, "BAD_REQUEST"),
)


def error_body(code: str, message: str, details: dict[str, JsonValue] | None = None) -> JsonValue:
    return {"error": {"code": code, "message": message, "details": details or {}}}


async def _framework_error(request: Request, exc: Exception) -> JSONResponse:
    for error_type, status, code in ERROR_MAP:
        if isinstance(exc, error_type):
            details: dict[str, JsonValue] = {}
            if isinstance(exc, RunFailedError):
                details["run_id"] = exc.run_id
            return JSONResponse(status_code=status, content=error_body(code, str(exc), details))
    raise exc  # pragma: no cover - only IndustrialAIError is registered


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors: list[JsonValue] = [
        {"loc": [str(p) for p in e.get("loc", ())], "msg": str(e.get("msg", ""))}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_body("VALIDATION_ERROR", "request validation failed", {"errors": errors}),
    )


async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content=error_body("INTERNAL_ERROR", "internal error"))


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(IndustrialAIError, _framework_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unexpected_error)
