from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, get_db, verify_csrf_header
from app.db.models import User
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
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        # FIX 3: authenticated callers contribute their own private runs to
        # the evidence pool; anonymous callers see public runs only.
        return RecommendationEngine.recommend(db=db, req=req, current_user=current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
