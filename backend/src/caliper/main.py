import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from caliper.adapters.opencode.runtime import OpenCodeRuntime
from caliper.adapters.postgres.database import SessionLocal, engine
from caliper.adapters.postgres.opencode_settings_repository import (
    SqlOpenCodeSettingsRepository,
)
from caliper.adapters.postgres.task_runner import PostgresTaskRunner
from caliper.adapters.secret_store.factory import configured_secret_store
from caliper.adapters.task_handlers import handle_persisted_task
from caliper.api.auth import router as auth_router
from caliper.api.credentials import router as credentials_router
from caliper.api.ollama_provider import router as ollama_provider_router
from caliper.api.opencode_provider import router as opencode_provider_router
from caliper.api.projects import router as projects_router
from caliper.api.repository_sync import router as repository_sync_router
from caliper.application.secret_store import SecretStoreError


@asynccontextmanager
async def lifespan(app: FastAPI):
    opencode = OpenCodeRuntime(
        base_url=os.environ.get("OPENCODE_BASE_URL", "http://127.0.0.1:4096")
    )
    try:
        async with SessionLocal() as session:
            settings = await SqlOpenCodeSettingsRepository(session).get()
        if settings.auth_secret_ref:
            opencode.write_profile(configured_secret_store().get(settings.auth_secret_ref))
    except (SecretStoreError, ValueError):
        opencode.profile_error = True
    await opencode.start()
    app.state.opencode_secret_store = configured_secret_store()
    app.state.opencode_runtime = opencode
    runner = PostgresTaskRunner(SessionLocal, engine, handle_persisted_task)
    app.state.task_runner = runner
    await runner.start()
    try:
        yield
    finally:
        await runner.stop()
        await opencode.stop()
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
app.include_router(ollama_provider_router)
app.include_router(opencode_provider_router)


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
