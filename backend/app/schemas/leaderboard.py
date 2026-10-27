from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeaderboardItem(BaseModel):
    model_id: str
    model_name: str
    domain: str
    task_type: str
    dataset_id: str | None = None
    primary_metric_name: str
    primary_metric_value: float
    avg_latency_ms: float | None = None
    vram_weight_gb: float | None = None
    run_id: str
    sample_count: int | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

class LeaderboardGroup(BaseModel):
    """FIX 7: one comparable evaluation cohort. Rank numbers inside a group
    only ever compare runs sharing dataset, protocol, split AND the exact
    evaluated sample IDs."""

    dataset_id: str
    protocol_id: str
    split: str
    sample_count: int | None = None
    primary_metric_name: str
    # Stable identity for consumers (e.g. React keys): hash of the exact
    # evaluated sample IDs. Two groups with equal sample_count but different
    # sample sets get different keys.
    cohort_id: str = ""
    items: list[LeaderboardItem] = Field(default_factory=list)

class LeaderboardResponse(BaseModel):
    domain: str | None = None
    task_type: str | None = None
    groups: list[LeaderboardGroup] = Field(default_factory=list)
    items: list[LeaderboardItem] = Field(default_factory=list)  # deprecated flat view (legacy consumers)
    total: int
