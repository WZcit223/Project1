"""The UI gets scenario and parameter metadata only from the Application API.

A stub API (httpx2 MockTransport) serves a made-up pack whose scenario parameters are not warehouse
parameters; the scenario builder must render and submit exactly those, proving it depends on the API
response, not on scenario-pack or framework code.
"""

import json
from typing import Any
from urllib.parse import urlencode

import httpx2
from fastapi.testclient import TestClient

from industrial_ai_ui.app import create_ui_app
from industrial_ai_ui.client import ApiClient

SCHEMA = {
    "properties": {
        "spindle_speed_factor": {"type": "number", "default": 1.0, "minimum": 0.5, "maximum": 2.0},
        "maintenance_window_days": {"type": "integer", "default": 0, "minimum": 0},
    }
}
SPEC = {
    "scenario_id": "nominal",
    "version": "1.0.0",
    "pack": "machining",
    "title": "Nominal",
    "parameters": {},
    "source": "pack",
}


def stub_api(posted: list[Any]) -> ApiClient:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.method == "POST" and request.url.path == "/api/scenarios":
            body = json.loads(request.content)
            posted.append(body)
            return httpx2.Response(201, json={**body, "source": "user"})
        if request.url.path == "/api/scenarios":
            return httpx2.Response(200, json=[SPEC])
        if request.url.path == "/api/scenarios/nominal":
            return httpx2.Response(
                200, json={"spec": SPEC, "effective_parameters": {}, "parameter_schema": SCHEMA}
            )
        return httpx2.Response(404, json={"error": {"code": "NOT_FOUND", "message": "stub"}})

    return ApiClient(
        httpx2.AsyncClient(transport=httpx2.MockTransport(handler), base_url="http://stub")
    )


def test_scenario_builder_is_driven_by_api_metadata() -> None:
    posted: list[Any] = []
    browser = TestClient(create_ui_app(stub_api(posted), pack="machining"))
    page = browser.get("/scenarios").text
    assert 'name="param_spindle_speed_factor"' in page and 'max="2.0"' in page
    assert 'name="param_maintenance_window_days"' in page
    assert "demand_multiplier" not in page  # nothing warehouse-specific is hard-coded

    fields = [
        ("scenario_id", "fast_spindle"),
        ("version", "1.0.0"),
        ("param_spindle_speed_factor", "1.5"),
        ("param_maintenance_window_days", "0"),
    ]
    response = browser.post(
        "/scenarios",
        content=urlencode(fields),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 201
    (body,) = posted
    assert body["pack"] == "machining"
    assert body["parameters"] == {
        "spindle_speed_factor": 1.5
    }  # only values that differ from defaults
