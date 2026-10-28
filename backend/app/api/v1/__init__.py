from fastapi import APIRouter

from app.api.v1 import (
    alerts,
    audit_logs,
    auth,
    datasets,
    firewall,
    health,
    incidents,
    investigation,
    models,
    recommendations,
    users,
)

api_router = APIRouter(prefix="/api/v1")
for module in (
    health,
    auth,
    users,
    models,
    datasets,
    alerts,
    investigation,
    incidents,
    recommendations,
    firewall,
    audit_logs,
):
    api_router.include_router(module.router)
