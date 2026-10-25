from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_csrf_header
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation_engine import RecommendationEngine

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post(
    "",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_csrf_header)],
)
def get_recommendations(
    req: RecommendationRequest,
    db: Session = Depends(get_db),
):
    try:
        return RecommendationEngine.recommend(db=db, req=req)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
