"""Fine-tuning service entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from .database import init_db, recover_running_jobs
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown.

    Initialises the database and recovers any jobs that were
    left in a running state from a previous crash.

    Args:
        app: The FastAPI application instance.

    Yields:
        None
    """
    init_db()
    recover_running_jobs()
    yield


app = FastAPI(
    title="Splinter Fine-Tuning Service",
    lifespan=lifespan,
)
app.include_router(router, prefix="/v1/fine_tuning")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        A dictionary with status ok.
    """
    return {"status": "ok"}
