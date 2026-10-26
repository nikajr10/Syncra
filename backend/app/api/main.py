import logging
import threading
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api import actions, admin, auth, chat
from app.config.settings import get_models_config, get_settings
from app.monitor import setup_logging

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

# The API documentation: Swagger UI at /docs and ReDoc at /redoc, both built from these and
# from each endpoint's summary, docstring and response model. Only served when API_DOCS is on.
DESCRIPTION = """
Syncra answers questions about your team's GitHub, Jira and Slack, and shows its sources.

**Logging in here.** An admin creates your user with `make add-user`. Open **POST /auth/login**,
click *Try it out*, send your username and password, and copy the `token` from the answer. Then
click **Authorize** (top right), paste the token and close the dialog: every endpoint now runs
as you, until the token expires or you log out.
"""
TAGS = [
    {"name": "Login", "description": "Log in for a token, log out, and see who you are."},
    {
        "name": "Chat",
        "description": "Your chats and their messages. You only ever see your own chats.",
    },
    {
        "name": "Actions",
        "description": "Approval cards: what Syncra offered to do for you. Nothing runs until "
        "you approve it.",
    },
    {
        "name": "Admin",
        "description": "Admins only: connect sources, watch them sync, link people's accounts.",
    },
    {"name": "Health", "description": "Is the API up? No login needed."},
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Fail fast at startup with a clear message if configuration is missing.
    get_settings()
    get_models_config()
    setup_logging()
    if get_settings().warm_up:  # in the background: the API answers at once
        from app.models.gateway import warm_up

        threading.Thread(target=warm_up, name="warm-up", daemon=True).start()
    yield


_docs = get_settings().api_docs
app = FastAPI(
    title="Syncra API",
    description=DESCRIPTION,
    openapi_tags=TAGS,
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


@app.get("/health", tags=["Health"], summary="Is the API up?")
def health() -> Health:
    return Health()


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(actions.router)
app.include_router(admin.router)
