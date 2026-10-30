"""H-Caliper v1 API router."""

from fastapi import APIRouter

from app.api.v1 import (
    approvals,
    audit,
    auth,
    caliper,
    dashboard,
    environments,
    health,
    notifications,
    projects,
    providers,
    tasks,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(environments.router)
api_router.include_router(providers.router)
api_router.include_router(caliper.router)
api_router.include_router(tasks.router)
api_router.include_router(approvals.router)
api_router.include_router(audit.router)
api_router.include_router(dashboard.router)
api_router.include_router(notifications.router)
