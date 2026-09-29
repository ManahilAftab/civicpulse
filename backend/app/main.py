"""App factory, middleware, error handlers and lifecycle.

Graceful shutdown: on SIGTERM, uvicorn stops accepting new connections, waits for
in-flight requests to finish (bounded by --timeout-graceful-shutdown), then runs
the lifespan shutdown below, which closes the Postgres pool, Redis and the triage
executor. Kubernetes' preStop sleep removes the pod from endpoints first.
"""

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.container import Container, build_container
from app.errors import ComplaintNotFound, InvalidTransition, RateLimitExceeded
from app.logging_config import configure_logging, request_id_ctx
from app.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.routes import complaints, health, meta, stats

log = logging.getLogger("civicpulse")


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        log.info(
            "startup", extra={"triage_provider": app.state.container.triage_service.primary.name}
        )
        yield
        log.info("shutdown: draining complete, closing pools")
        app.state.container.close()

    app = FastAPI(title="CivicPulse API", version="0.1.0", lifespan=lifespan)
    app.state.container = container or build_container(settings)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")  # template, not raw URL: bounded labels
            REQUEST_COUNT.labels(request.method, path, str(status)).inc()
            REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
            if path not in ("/health", "/ready", "/metrics"):
                log.info(
                    "request",
                    extra={
                        "method": request.method,
                        "path": path,
                        "status": status,
                        "duration_ms": int(elapsed * 1000),
                    },
                )
            request_id_ctx.reset(token)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                # Malformed JSON has no field; its loc is a character offset, so say "body".
                "field": "body"
                if err["type"] == "json_invalid"
                else ".".join(str(p) for p in err["loc"] if p not in ("body", "query", "path"))
                or "body",
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=400, content={"detail": "Validation failed", "errors": errors}
        )

    @app.exception_handler(ComplaintNotFound)
    async def not_found(_: Request, exc: ComplaintNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidTransition)
    async def invalid_transition(_: Request, exc: InvalidTransition) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(RateLimitExceeded)
    async def rate_limited(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": str(exc)},
            headers={"Retry-After": str(exc.retry_after_s)},
        )

    app.include_router(complaints.router)
    app.include_router(stats.router)
    app.include_router(meta.router)
    app.include_router(health.router)

    def openapi_without_422() -> dict:
        # FastAPI documents 422 by default, but this API answers validation errors with 400.
        # The frontend client is generated from this schema, so it must match reality.
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        for operations in schema.get("paths", {}).values():
            for operation in operations.values():
                responses = operation.get("responses", {})
                if responses.pop("422", None) is not None:
                    responses.setdefault(
                        "400",
                        {
                            "description": "Validation error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    )
        app.openapi_schema = schema
        return schema

    app.openapi = openapi_without_422  # type: ignore[method-assign]
    return app


# Run with: uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
# (--factory means importing this module never connects to anything, which keeps tests hermetic.)
