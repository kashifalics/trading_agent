import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.database.init_db import init_db

log = logging.getLogger("app")
API_DESCRIPTION = (
    "AI Trading Intelligence Platform - ANALYSIS ONLY. No order execution, no broker connectivity. "
    "Decisions are BUY / SELL / WAIT with evidence; probabilities are only shown when genuinely calibrated and validated."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    s = get_settings()
    s.validate_for_runtime()
    init_db()
    if s.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=s.sentry_dsn, environment=s.app_env)
        except ImportError:
            log.warning("SENTRY_DSN set but sentry-sdk is not installed")
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="AI Trading Intelligence API", version="0.1.0", description=API_DESCRIPTION, lifespan=lifespan,
                  docs_url="/docs", openapi_url="/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=[s.frontend_url, "http://localhost:3000", "http://127.0.0.1:3000"],
                       allow_methods=["GET", "POST", "DELETE", "PATCH"], allow_headers=["*"], allow_credentials=False)

    hits: dict[str, deque] = defaultdict(deque)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        path = request.url.path
        if path.startswith("/api/") and not path.endswith("/health"):
            ip = request.client.host if request.client else "unknown"
            q, now, limit = hits[ip], time.monotonic(), get_settings().rate_limit_per_minute
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= limit:
                return JSONResponse(status_code=429, headers={"Retry-After": "30", "x-request-id": rid}, content={
                    "error": {"code": "rate_limited", "message": "Too many requests", "details": {}, "request_id": rid}})
            q.append(now)
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"error": {
            "code": exc.code, "message": exc.message, "details": exc.details,
            "request_id": getattr(request.state, "request_id", None)}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(x) for x in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"error": {
            "code": "validation_failed", "message": "Request validation failed", "details": {"errors": details},
            "request_id": getattr(request.state, "request_id", None)}})

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse(status_code=500, content={"error": {
            "code": "internal_error", "message": "Internal server error", "details": {},
            "request_id": getattr(request.state, "request_id", None)}})

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
