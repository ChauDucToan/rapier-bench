from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.benchmarks import router as benchmarks_router
from app.api.comparisons import router as comparisons_router
from app.api.datasets import router as datasets_router
from app.api.leaderboard import router as leaderboard_router
from app.api.models import router as models_router
from app.api.recommendations import router as recommendations_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(models_router)
api_v1_router.include_router(datasets_router)
api_v1_router.include_router(benchmarks_router)
api_v1_router.include_router(comparisons_router)
api_v1_router.include_router(leaderboard_router)
api_v1_router.include_router(recommendations_router)

__all__ = ["api_v1_router"]
