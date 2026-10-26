import logging
import threading
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.routes import actions, admin, auth, chat
from app.core.config import get_models_config, get_settings
from app.core.monitor import setup_logging

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

# Swagger UI at /docs and ReDoc at /redoc; only served when API_DOCS is on.
DESCRIPTION = "Authenticate with `POST /auth/login`, then click **Authorize** and paste the token."
TAGS = [
    {"name": "Auth"},
    {"name": "Chats"},
    {"name": "Actions"},
    {"name": "Sources", "description": "Admin only."},
    {"name": "Users", "description": "Admin only."},
    {"name": "Status", "description": "Admin only."},
    {"name": "Health"},
]
SWAGGER_UI = {
    "defaultModelsExpandDepth": -1,  # hide the Schemas section
    "displayRequestDuration": True,
    "filter": True,
    "persistAuthorization": True,
    "tryItOutEnabled": True,
}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Fail fast at startup with a clear message if configuration is missing.
    get_settings()
    get_models_config()
    setup_logging()
    if get_settings().warm_up:  # in the background: the API answers at once
        from app.ml.gateway import warm_up

        threading.Thread(target=warm_up, name="warm-up", daemon=True).start()
    yield


_docs = get_settings().api_docs
app = FastAPI(
    title="Syncra API",
    description=DESCRIPTION,
    openapi_tags=TAGS,
    swagger_ui_parameters=SWAGGER_UI,
    generate_unique_id_function=lambda route: route.name,  # operationId = function name
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


class Health(BaseModel):
    status: str = "ok"


@app.get("/health", tags=["Health"], summary="Health check")
def health() -> Health:
    return Health()


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(actions.router)
app.include_router(admin.router)
