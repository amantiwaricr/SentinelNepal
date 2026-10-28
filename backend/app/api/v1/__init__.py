from fastapi import APIRouter

from app.api.v1 import alerts, auth, datasets, health, investigation, models, users

api_router = APIRouter(prefix="/api/v1")
for module in (health, auth, users, models, datasets, alerts, investigation):
    api_router.include_router(module.router)
