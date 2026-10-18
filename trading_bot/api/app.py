"""FastAPI application — dashboard API + UI."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from trading_bot import __version__
from trading_bot.config.settings import get_settings, reload_settings
from trading_bot.utils.exceptions import TradingBotError
from trading_bot.utils.logging import setup_logging

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

_engine = None


def get_engine() -> Any:
    global _engine
    if _engine is None:
        from trading_bot.services.engine import TradingEngine

        _engine = TradingEngine(get_settings())
    return _engine


def reset_engine() -> None:
    global _engine
    _engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    settings = get_settings()
    setup_logging(settings.log_level)
    yield


app = FastAPI(
    title="AI Stock Trading Bot",
    version=__version__,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.exception_handler(TradingBotError)
async def trading_error_handler(request: Request, exc: TradingBotError) -> JSONResponse:
    return JSONResponse(status_code=400, content=exc.to_dict())


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"version": __version__},
    )


@app.get("/api/health")
async def health() -> dict[str, Any]:
    settings = get_settings()
    engine = get_engine()
    broker_health = engine.broker.health_check()
    return {
        "ok": True,
        "version": __version__,
        "trading_mode": settings.trading_mode.value,
        "broker": broker_health,
        "setup": settings.setup_status(),
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    snap = get_engine().status()
    return snap.model_dump(mode="json")


@app.post("/api/run")
async def run_once(dry_run: bool = False) -> dict[str, Any]:
    snap = get_engine().run_once(submit_orders=not dry_run)
    return snap.model_dump(mode="json")


@app.get("/api/setup")
async def setup() -> dict[str, Any]:
    return get_settings().setup_status()


@app.post("/api/risk/reset-kill-switch")
async def reset_kill(confirm: str = "") -> dict[str, Any]:
    engine = get_engine()
    try:
        engine.risk.reset_kill_switch(confirm=confirm)
    except TradingBotError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    return {"ok": True, "risk": engine.risk.snapshot()}


@app.get("/api/validation/latest")
async def validation_latest() -> dict[str, Any]:
    path = get_settings().cache_dir / "validation_report.json"
    if not path.exists():
        return {
            "ok": False,
            "guidance": (
                "No validation report yet. Run `make sample-validation` or "
                "`python -m trading_bot.cli validate`."
            ),
        }
    import json

    return {"ok": True, "report": json.loads(path.read_text(encoding="utf-8"))}


@app.post("/api/validation/run")
async def validation_run() -> dict[str, Any]:
    """Trigger a (potentially slow) validation job synchronously for demo sizes."""
    import json
    from datetime import datetime

    from trading_bot.data.provider import YFinanceProvider
    from trading_bot.validation.walk_forward import run_walk_forward

    settings = get_settings()
    # Smaller universe for API-triggered runs
    symbols = settings.yaml.universe.etfs[:6] + settings.yaml.universe.large_caps[:6]
    provider = YFinanceProvider(cache_dir=settings.cache_dir)
    close = provider.get_close_panel(symbols, start="2019-01-01", end=datetime.utcnow().strftime("%Y-%m-%d"))
    result = run_walk_forward(close, settings)
    payload = result.to_dict()
    out = settings.cache_dir / "validation_report.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return {"ok": True, "report": payload, "guidance": result.guidance}


@app.post("/api/reload-settings")
async def reload() -> dict[str, Any]:
    reload_settings()
    reset_engine()
    return {"ok": True, "setup": get_settings().setup_status()}


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "trading_bot.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env == "development",
    )


if __name__ == "__main__":
    run()
