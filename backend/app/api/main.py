import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.config.settings import get_models_config, get_settings

log = logging.getLogger("syncra.api")

# Sent on every response. The API serves JSON only, so the CSP can forbid everything;
# /docs (local only, API_DOCS=true) loads Swagger UI from a CDN and gets no CSP.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Cross-Origin-Resource-Policy": "same-origin",
}
STRICT_CSP = "default-src 'none'; frame-ancestors 'none'"
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Fail fast at startup with a clear message if configuration is missing.
    get_settings()
    get_models_config()
    yield


_docs = get_settings().api_docs
app = FastAPI(
    title="Syncra",
    lifespan=lifespan,
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)


@app.middleware("http")
async def security(request: Request, call_next: Callable[[Request], Awaitable[Response]]):
    """Security headers + a correlation id on every response; unhandled errors -> generic 500."""
    request_id = uuid.uuid4().hex
    try:
        response = await call_next(request)
    except Exception:
        # Details stay in the server log; the client only gets the id to quote.
        log.exception(
            "unhandled error request_id=%s %s %s", request_id, request.method, request.url.path
        )
        response = JSONResponse({"detail": "Internal server error", "request_id": request_id}, 500)
    response.headers.update(SECURITY_HEADERS)
    if not request.url.path.startswith(DOCS_PATHS):
        response.headers["Content-Security-Policy"] = STRICT_CSP
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
