from pydantic import BaseModel, Field


class RecommendationConstraints(BaseModel):
    max_vram_gb: float | None = None
    max_latency_ms: float | None = None
    min_quality: float | None = None


class RecommendationWeights(BaseModel):
    quality: float = 0.5
    latency: float = 0.3
    vram: float = 0.2


class RecommendationRequest(BaseModel):
    domain: str
    task_type: str | None = None
    constraints: RecommendationConstraints | None = None
    weights: RecommendationWeights | None = None


class RecommendationModelBreakdown(BaseModel):
    model_id: str
    model_name: str
    composite_score: float
    quality_score: float
    latency_ms: float | None = None
    vram_gb: float
    normalized_quality: float
    normalized_latency: float | None = None
    normalized_vram: float
    run_id: str


class RecommendationResponse(BaseModel):
    status: str
    domain: str
    task_type: str | None = None
    recommendations: list[RecommendationModelBreakdown] = Field(default_factory=list)
    eligible_count: int
    limitations: list[str] = Field(default_factory=list)
    explanation: str
