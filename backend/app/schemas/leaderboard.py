from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeaderboardItem(BaseModel):
    model_id: str
    model_name: str
    domain: str
    task_type: str
    primary_metric_name: str
    primary_metric_value: float
    avg_latency_ms: float | None = None
    vram_weight_gb: float | None = None
    run_id: str
    sample_count: int
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class LeaderboardResponse(BaseModel):
    domain: str | None = None
    task_type: str | None = None
    items: list[LeaderboardItem] = Field(default_factory=list)
    total: int
