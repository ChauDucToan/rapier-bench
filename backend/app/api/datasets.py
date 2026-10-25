from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.dataset import DatasetResponse
from app.services.benchmark_service import BenchmarkService

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=list[DatasetResponse])
def list_datasets(
    domain: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return BenchmarkService.list_datasets(db=db, domain=domain, limit=limit, offset=offset)


@router.get("/{id}", response_model=DatasetResponse)
def get_dataset(
    id: str,
    db: Session = Depends(get_db),
):
    dataset = BenchmarkService.get_dataset(db=db, dataset_id=id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{id}' not found",
        )
    return dataset
