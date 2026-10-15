from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.settings import get_models_config, get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Fail fast at startup with a clear message if configuration is missing.
    get_settings()
    get_models_config()
    yield


app = FastAPI(title="Syncra", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
