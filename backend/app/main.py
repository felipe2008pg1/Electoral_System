import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.routes.vote import router as vote_router
from app.api.routes.ws import router as ws_router
from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.session import engine
from app.services.results_broadcaster import run_broadcaster

settings = get_settings()

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)
logger = logging.getLogger("electoral_system")

_stop_event = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_broadcaster(_stop_event))
    try:
        yield
    finally:
        _stop_event.set()
        await task


app = FastAPI(
    title="Secure Electoral System",
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(vote_router)
app.include_router(ws_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception", extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
async def health() -> dict:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        logger.exception("Health check failed")
        return {"status": "degraded"}