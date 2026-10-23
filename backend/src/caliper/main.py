from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from caliper.adapters.postgres.database import engine
from caliper.api.projects import router as projects_router


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
