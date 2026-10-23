from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from caliper.adapters.postgres.database import engine
from caliper.api.auth import router as auth_router
from caliper.api.credentials import router as credentials_router
from caliper.api.projects import router as projects_router
from caliper.api.repository_sync import router as repository_sync_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Caliper API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.include_router(projects_router)
app.include_router(auth_router)
app.include_router(credentials_router)
app.include_router(repository_sync_router)


@app.middleware("http")
async def reject_cross_origin_mutations(request: Request, call_next) -> Response:
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse(status_code=403, content={"detail": "Request origin rejected"})
    return await call_next(request)


@app.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="PostgreSQL is not ready") from error
    return {"status": "ready"}
