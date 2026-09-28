"""Gate 11: the Golden Path is executable from the browser UI, which uses only the Application API.

The UI app is mounted into the API app exactly as ``scripts/serve.py`` does and exercised with plain
form posts (what a browser sends), plus HTMX requests where the page uses them.
"""

import ast
import html
import re
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlencode

import httpx2
import pytest
from fastapi.testclient import TestClient

from industrial_ai.api.app import create_app
from industrial_ai.core.config import Environment, Settings
from industrial_ai_ui.app import create_ui_app
from industrial_ai_ui.client import ApiClient

ROOT = Path(__file__).resolve().parents[2]
UI_SOURCE = ROOT / "ui" / "src" / "industrial_ai_ui"
FIXTURE = ROOT / "tests" / "fixtures" / "m5_like"
FORM = {"content-type": "application/x-www-form-urlencoded"}


@pytest.fixture(scope="module")
def browser(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    root = tmp_path_factory.mktemp("ui")
    settings = Settings(
        env=Environment.TEST,
        data_dir=root,
        database_url=f"sqlite:///{root / 'ui.sqlite'}",
        reference_dirs={"fixture": FIXTURE, "broken": root / "missing"},
    )
    api = create_app(settings)
    transport = httpx2.ASGITransport(app=api)
    client = ApiClient(httpx2.AsyncClient(transport=transport, base_url="http://api"))
    api.mount("/ui", create_ui_app(client))
    with TestClient(api) as test_client:
        yield test_client


def post_form(
    browser: TestClient,
    path: str,
    fields: list[tuple[str, str]],
    headers: dict[str, str] | None = None,
) -> httpx2.Response:
    return browser.post(
        path,
        content=urlencode(fields),
        headers={**FORM, **(headers or {})},
        follow_redirects=False,
    )


def run_form(scenario_id: str, reference_id: str = "fixture") -> list[tuple[str, str]]:
    return [
        ("reference_id", reference_id),
        ("scenario_id", scenario_id),
        ("forecast_model", "seasonal_naive"),
        ("strategies", "reorder_point"),
        ("strategies", "safety_stock"),
        ("strategies", "dynamic"),
        ("horizon_days", "56"),
        ("seed", "20260927"),
    ]


def test_ui_code_imports_no_framework_module() -> None:
    offending = []
    for path in UI_SOURCE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            offending += [
                f"{path.name}: {n}"
                for n in names
                if n.split(".")[0] in {"industrial_ai", "industrial_ai_warehouse"}
            ]
    assert offending == []


def test_pages_render(browser: TestClient) -> None:
    for path in ("/ui/", "/ui/data", "/ui/synthetic", "/ui/scenarios", "/ui/simulate", "/ui/runs"):
        response = browser.get(path)
        assert response.status_code == 200, path
        assert "Prototype · Synthetic data" in response.text
    assert "No runs yet" in browser.get("/ui/").text
    assert browser.get("/ui/static/vendor/htmx-2.0.4.min.js").status_code == 200


def test_golden_path_from_the_browser(browser: TestClient) -> None:
    run_pages = {}
    for scenario_id in ("baseline", "high_demand", "demand_shock", "supply_disruption"):
        response = post_form(browser, "/ui/simulate", run_form(scenario_id))
        assert response.status_code == 303, response.text
        page = browser.get(response.headers["location"])
        assert page.status_code == 200
        for text in ("Fill rate", "Total cost", "Reorder point", "Safety stock", "Dynamic", "<svg"):
            assert text in page.text
        run_pages[scenario_id] = response.headers["location"]
    overview = browser.get("/ui/").text
    assert "fill rate" in overview and "<svg" in overview

    run_ids = [url.rstrip("/").rsplit("/", 1)[1] for url in run_pages.values()]
    compare = browser.get("/ui/compare", params=[("run_ids", r) for r in run_ids])
    assert compare.status_code == 200
    for scenario_id in run_pages:
        assert scenario_id in compare.text

    runs = browser.get("/ui/runs").text
    assert all(r in runs for r in run_ids)
    run_page = browser.get(run_pages["high_demand"]).text
    dataset_id = run_page.split("/ui/data/")[1].split('"')[0]
    assert "Provenance" in browser.get(f"/ui/data/{dataset_id}").text


def test_htmx_submission_redirects_via_header(browser: TestClient) -> None:
    response = post_form(
        browser, "/ui/simulate", run_form("baseline"), headers={"HX-Request": "true"}
    )
    assert response.status_code == 204
    assert response.headers["HX-Redirect"].startswith("http://testserver/ui/runs/run_")


def test_what_if_reruns_with_one_parameter_changed(browser: TestClient) -> None:
    first = post_form(browser, "/ui/simulate", run_form("baseline")).headers["location"]
    run_id = first.rstrip("/").rsplit("/", 1)[1]
    second = post_form(
        browser, f"/ui/runs/{run_id}/what-if", [("parameter", "lead_time_delta"), ("value", "5")]
    )
    assert second.status_code == 303
    page = browser.get(second.headers["location"]).text
    assert "lead_time_delta" in page and "5" in page
    new_id = second.headers["location"].rstrip("/").rsplit("/", 1)[1]
    before = browser.get(f"/api/runs/{run_id}").json()
    after = browser.get(f"/api/runs/{new_id}").json()
    assert after["scenario_overrides"] == {"lead_time_delta": 5}
    assert after["scenario"]["version"] == before["scenario"]["version"]  # pinned
    for key in ("reference_id", "scenario_id", "seed", "horizon_days", "options"):
        assert after["request"][key] == before["request"][key], key
    assert "reference" not in after["request"]


def test_scenario_builder_saves_a_usable_scenario(browser: TestClient) -> None:
    fields = [
        ("scenario_id", "ui_promo"),
        ("version", "1.0.0"),
        ("title", "UI promotion"),
        ("param_shock_multiplier", "1.8"),
        ("param_shock_start_day", "7"),
        ("param_shock_duration_days", "7"),
        ("param_demand_multiplier", "1.0"),
    ]
    saved = post_form(browser, "/ui/scenarios", fields)
    assert saved.status_code == 201 and "Saved" in saved.text
    duplicate = post_form(browser, "/ui/scenarios", fields)
    assert duplicate.status_code == 409 and "already registered" in duplicate.text
    changed = [*fields[:1], ("version", "1.0.1"), ("param_demand_multiplier", "99")]
    invalid = post_form(browser, "/ui/scenarios", changed)
    assert invalid.status_code == 422
    assert "ui_promo" in browser.get("/ui/simulate").text
    run = post_form(browser, "/ui/simulate", run_form("ui_promo"))
    assert run.status_code == 303
    assert "user-defined" in browser.get(run.headers["location"]).text


def test_errors_are_shown_not_hidden(browser: TestClient) -> None:
    failed = post_form(browser, "/ui/simulate", run_form("baseline", reference_id="broken"))
    assert failed.status_code == 500
    assert "stored as failed run run_" in failed.text
    missing = browser.get("/ui/runs/run_missing")
    assert missing.status_code == 404 and "RUN_NOT_FOUND" in missing.text


def test_synthetic_generation_page(browser: TestClient) -> None:
    page = browser.get("/ui/synthetic").text
    example = page.split('name="request_json" rows="22">')[1].split("</textarea>")[0]
    created = post_form(browser, "/ui/synthetic", [("request_json", html.unescape(example))])
    assert created.status_code == 201 and "Registered" in created.text
    bad = post_form(browser, "/ui/synthetic", [("request_json", "{not json")])
    assert bad.status_code == 422 and "Not valid JSON" in bad.text


def test_every_link_and_form_targets_the_ui(browser: TestClient) -> None:
    """Regression: UI route names must not resolve to same-named API routes (browser smoke test)."""
    record = post_form(browser, "/ui/simulate", run_form("baseline")).headers["location"]
    pages = [
        "/ui/",
        "/ui/data",
        "/ui/synthetic",
        "/ui/scenarios",
        "/ui/simulate",
        "/ui/runs",
        record,
    ]
    for path in pages:
        text = browser.get(path).text
        targets = re.findall(r'(?:href|action|hx-post)="(http://testserver[^"]*)"', text)
        assert targets, path
        for target in targets:
            assert target.startswith("http://testserver/ui/"), (path, target)


def test_forms_work_when_submitted_to_their_rendered_action(browser: TestClient) -> None:
    page = browser.get("/ui/scenarios").text
    action = re.search(r'<form method="post" action="([^"]+)"', page)
    assert action is not None
    fields = [
        ("scenario_id", "action_check"),
        ("version", "1.0.0"),
        ("param_shock_multiplier", "1.5"),
    ]
    response = post_form(browser, action.group(1).replace("http://testserver", ""), fields)
    assert response.status_code == 201 and "Saved" in response.text


def test_default_simulation_form_matches_the_documented_demo(browser: TestClient) -> None:
    """First-run reproducibility: an untouched form uses the demo's model, horizon and seed."""
    page = browser.get("/ui/simulate").text
    selected = re.search(r'<option value="([a-z_]+)"\s+selected>', page)
    assert selected is not None and selected.group(1) == "seasonal_naive"
    assert 'name="horizon_days" min="7" max="366" value="91"' in page
    assert 'name="seed" value="20260927"' in page
