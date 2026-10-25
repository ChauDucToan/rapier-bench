from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.model import ModelResponse
from app.services.benchmark_service import BenchmarkService

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelResponse])
def list_models(
    domain: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return BenchmarkService.list_models(db=db, domain=domain, limit=limit, offset=offset)


@router.get("/{id}", response_model=ModelResponse)
def get_model(
    id: str,
    db: Session = Depends(get_db),
):
    model = BenchmarkService.get_model(db=db, model_id=id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{id}' not found",
        )
    return model
