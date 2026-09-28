"""UI application: pages rendered from Application API responses (docs/ui-spec.md §2)."""

import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from industrial_ai_ui import messages
from industrial_ai_ui.charts import Series, line_chart
from industrial_ai_ui.client import ApiClient, ApiError

HERE = Path(__file__).parent
DEFAULT_SEED = 20260927
EXAMPLE_GENERATION = {
    "generator_id": "rule_based",
    "dataset_id": "ui_example_suppliers",
    "output_schema": {
        "schema_id": "ui.supplier",
        "schema_version": "1.0.0",
        "fields": [
            {"name": "supplier_id", "dtype": "str"},
            {"name": "order_cost", "dtype": "float", "min": 0},
        ],
        "primary_key": ["supplier_id"],
    },
    "seed": 1,
    "size": {"rows": 5},
    "parameters": {
        "columns": {
            "supplier_id": {"kind": "sequence", "prefix": "SUP"},
            "order_cost": {"kind": "uniform", "low": 20, "high": 60, "decimals": 2},
        }
    },
}


def strategy_rank(strategy_id: str) -> int:
    """Display order: known strategies as in the message catalog, others after them."""
    order = list(messages.STRATEGY_LABELS)
    return order.index(strategy_id) if strategy_id in order else len(order)


def format_metric(value: Any, metric_id: str) -> str:
    if value is None:
        return "–"
    number = float(value)
    if metric_id in messages.RATIO_METRICS:
        return f"{number:.1%}"
    if metric_id in messages.MONEY_METRICS:
        return f"${number:,.0f}"
    return f"{number:,.2f}" if abs(number) < 100 else f"{number:,.0f}"


async def form_data(request: Request) -> dict[str, list[str]]:
    """URL-encoded form fields (HTMX and plain HTML forms)."""
    return parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)


def first(form: dict[str, list[str]], name: str, default: str = "") -> str:
    return form.get(name, [default])[0]


def create_ui_app(api: ApiClient, pack: str = "warehouse") -> FastAPI:
    """UI app for one scenario pack; ``api`` is its only data source."""
    app = FastAPI(title="Industrial AI — Demo UI", docs_url=None, redoc_url=None, openapi_url=None)
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.filters["metric"] = format_metric
    templates.env.globals.update(
        messages=messages, metric_label=lambda m: messages.METRIC_LABELS.get(m, m)
    )
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    def page(request: Request, name: str, status_code: int = 200, **context: Any) -> HTMLResponse:
        return templates.TemplateResponse(request, name, context, status_code=status_code)

    def redirect(request: Request, url: str) -> Response:
        if request.headers.get("HX-Request"):
            return Response(status_code=204, headers={"HX-Redirect": url})
        return RedirectResponse(url, status_code=303)

    async def run_view(run_id: str) -> dict[str, Any]:
        results = await api.get(f"/api/runs/{run_id}/results")
        results["variants"] = dict(
            sorted(results["variants"].items(), key=lambda item: strategy_rank(item[0]))
        )
        record = await api.get(f"/api/runs/{run_id}")
        charts: list[str] = []
        variants = list(results["variants"])
        if variants:

            async def series(variant: str, column: str) -> Series:
                data = await api.get(
                    f"/api/runs/{run_id}/timeseries",
                    params={"variant": variant, "table": "inventory_ledger", "column": column},
                )
                points = [(date.fromisoformat(p["date"]), p["value"]) for p in data["points"]]
                return Series(messages.STRATEGY_LABELS.get(variant, variant), points)

            demand = await series(variants[0], "demand")
            charts.append(line_chart([Series("Demand", demand.points)], "Daily demand (units)"))
            on_hand = [await series(v, "closing_on_hand") for v in variants]
            charts.append(line_chart(on_hand, "On-hand inventory by strategy (units)"))
            lost = [await series(v, "lost_sales") for v in variants]
            charts.append(line_chart(lost, "Unfulfilled demand by strategy (units / day)"))
        return {"results": results, "record": record, "charts": charts}

    async def latest_succeeded() -> str | None:
        for run in await api.get("/api/runs"):
            if run["status"] == "succeeded":
                return str(run["run_id"])
        return None

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> HTMLResponse:
        return page(request, "error.html", status_code=exc.status, error=exc)

    # --- pages -------------------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse, name="overview")
    async def overview(request: Request, run_id: str | None = None) -> HTMLResponse:
        run_id = run_id or await latest_succeeded()
        view = await run_view(run_id) if run_id else None
        return page(request, "overview.html", view=view)

    @app.get("/data", response_class=HTMLResponse, name="data")
    async def data(request: Request, source_type: str | None = None) -> HTMLResponse:
        params = {"source_type": source_type} if source_type else None
        datasets = await api.get("/api/datasets", params=params)
        return page(request, "data.html", datasets=datasets, source_type=source_type)

    @app.get("/data/{dataset_id}", response_class=HTMLResponse, name="dataset")
    async def dataset(request: Request, dataset_id: str) -> HTMLResponse:
        detail = await api.get(f"/api/datasets/{dataset_id}")
        preview = await api.get(f"/api/datasets/{dataset_id}/preview", params={"limit": 20})
        return page(request, "dataset.html", detail=detail, preview=preview)

    @app.get("/synthetic", response_class=HTMLResponse, name="synthetic")
    async def synthetic(request: Request) -> HTMLResponse:
        return page(
            request,
            "synthetic.html",
            generators=await api.get("/api/synthetic/generators"),
            request_json=json.dumps(EXAMPLE_GENERATION, indent=2),
            created=None,
            error=None,
        )

    @app.post("/synthetic", response_class=HTMLResponse, name="generate")
    async def generate(request: Request) -> HTMLResponse:
        text = first(await form_data(request), "request_json")
        generators = await api.get("/api/synthetic/generators")
        try:
            created = await api.post("/api/synthetic/generate", json.loads(text))
        except json.JSONDecodeError as exc:
            return page(
                request,
                "synthetic.html",
                422,
                generators=generators,
                request_json=text,
                created=None,
                error=f"Not valid JSON: {exc}",
            )
        except ApiError as exc:
            return page(
                request,
                "synthetic.html",
                exc.status,
                generators=generators,
                request_json=text,
                created=None,
                error=exc.message,
            )
        return page(
            request,
            "synthetic.html",
            201,
            generators=generators,
            request_json=text,
            created=created,
            error=None,
        )

    async def parameter_schema(scenario_id: str, version: str | None = None) -> dict[str, Any]:
        """The pack's scenario parameter JSON schema, as served by the Application API."""
        params = {"pack": pack, **({"version": version} if version else {})}
        detail = await api.get(f"/api/scenarios/{scenario_id}", params=params)
        schema: dict[str, Any] = detail["parameter_schema"]
        return schema

    async def scenario_context(error: str | None = None, saved: Any = None) -> dict[str, Any]:
        scenarios = await api.get("/api/scenarios", params={"pack": pack})
        schema = await parameter_schema(scenarios[0]["scenario_id"]) if scenarios else {}
        properties = schema.get("properties", {})
        return {
            "scenarios": scenarios,
            "schema": {"properties": properties},
            "defaults": {name: prop.get("default") for name, prop in properties.items()},
            "error": error,
            "saved": saved,
        }

    @app.get("/scenarios", response_class=HTMLResponse, name="scenarios")
    async def scenarios(request: Request) -> HTMLResponse:
        return page(request, "scenarios.html", **await scenario_context())

    @app.post("/scenarios", response_class=HTMLResponse, name="create_scenario")
    async def create_scenario(request: Request) -> HTMLResponse:
        form = await form_data(request)
        context = await scenario_context()
        parameters: dict[str, Any] = {}
        for name, prop in context["schema"]["properties"].items():
            raw = first(form, f"param_{name}")
            if raw == "":
                continue
            value: Any = raw == "on" if prop.get("type") == "boolean" else float(raw)
            if prop.get("type") == "integer":
                value = int(float(raw))
            if value != context["defaults"].get(name):
                parameters[name] = value
        spec = {
            "scenario_id": first(form, "scenario_id"),
            "version": first(form, "version", "1.0.0"),
            "pack": pack,
            "title": first(form, "title") or first(form, "scenario_id"),
            "description": first(form, "description"),
            "parameters": parameters,
            "tags": ["user"],
        }
        try:
            saved = await api.post("/api/scenarios", spec)
        except ApiError as exc:
            return page(
                request, "scenarios.html", exc.status, **await scenario_context(exc.message)
            )
        return page(request, "scenarios.html", 201, **await scenario_context(saved=saved))

    async def simulate_context(error: str | None = None, values: Any = None) -> dict[str, Any]:
        return {
            "references": await api.get("/api/references"),
            "scenarios": await api.get("/api/scenarios", params={"pack": pack}),
            "models": await api.get("/api/models", params={"pack": pack, "kind": "forecast"}),
            "strategies": sorted(
                await api.get("/api/strategies", params={"pack": pack}),
                key=lambda s: strategy_rank(s["component_id"]),
            ),
            "error": error,
            "values": values or {"horizon_days": 91, "seed": DEFAULT_SEED},
        }

    @app.get("/simulate", response_class=HTMLResponse, name="simulate")
    async def simulate(request: Request) -> HTMLResponse:
        return page(request, "simulate.html", **await simulate_context())

    @app.post("/simulate", name="start_run")
    async def start_run(request: Request) -> Response:
        form = await form_data(request)
        body = {
            "pack": pack,
            "reference_id": first(form, "reference_id") or None,
            "scenario_id": first(form, "scenario_id"),
            "seed": int(first(form, "seed", str(DEFAULT_SEED))),
            "horizon_days": int(first(form, "horizon_days", "91")),
            "options": {
                "forecast_model": first(form, "forecast_model", "seasonal_naive"),
                "strategies": form.get("strategies", []),
            },
        }
        try:
            record = await api.post("/api/runs", body)
        except ApiError as exc:
            message = exc.message
            if exc.code == "RUN_FAILED":
                message += f" (stored as failed run {exc.details.get('run_id')})"
            return page(
                request, "simulate.html", exc.status, **await simulate_context(message, body)
            )
        return redirect(request, str(request.url_for("run", run_id=record["run_id"])))

    @app.get("/runs", response_class=HTMLResponse, name="runs")
    async def runs(request: Request) -> HTMLResponse:
        return page(request, "runs.html", runs=await api.get("/api/runs"))

    @app.get("/runs/{run_id}", response_class=HTMLResponse, name="run")
    async def run(request: Request, run_id: str) -> HTMLResponse:
        view = await run_view(run_id)
        scenario = view["results"]["scenario"]
        schema = await parameter_schema(scenario["scenario_id"], scenario["version"])
        return page(request, "run.html", view=view, what_if_parameters=list(schema["properties"]))

    @app.post("/runs/{run_id}/what-if", name="what_if")
    async def what_if(request: Request, run_id: str) -> Response:
        """Re-run the same request with one scenario parameter changed.

        Same pack, reference id, scenario *version* (pinned to the one the original run used, even
        if a newer version exists), seed, horizon and options; earlier overrides are kept.
        """
        form = await form_data(request)
        record = await api.get(f"/api/runs/{run_id}")
        original = record["request"]
        name, number = first(form, "parameter"), float(first(form, "value"))
        value: float | int = int(number) if number.is_integer() else number
        body = {
            key: original[key]
            for key in ("pack", "reference_id", "scenario_id", "seed", "horizon_days", "options")
        }
        body["scenario_version"] = record["scenario"]["version"]
        body["scenario_overrides"] = {**original["scenario_overrides"], name: value}
        record = await api.post("/api/runs", body)
        return redirect(request, str(request.url_for("run", run_id=record["run_id"])))

    @app.get("/compare", response_class=HTMLResponse, name="compare")
    async def compare(request: Request) -> HTMLResponse:
        run_ids = request.query_params.getlist("run_ids")
        rows = (
            await api.get("/api/runs/compare", params={"run_ids": ",".join(run_ids)})
            if run_ids
            else []
        )
        columns = []
        for row in rows:
            column = (row["run_id"], row["scenario_id"])
            if column not in columns:
                columns.append(column)
        table: dict[str, dict[str, dict[str, Any]]] = {}
        for row in sorted(rows, key=lambda r: strategy_rank(r["variant"])):
            table.setdefault(row["variant"], {})[row["run_id"]] = row["metrics"]
        return page(request, "compare.html", columns=columns, table=table)

    return app
