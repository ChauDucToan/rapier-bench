from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.db.models import RunStatusEnum


class CreateBenchmarkRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    model_id: str = Field(..., max_length=128, pattern=r"^[a-zA-Z0-9_\-\./]+$")
    dataset_id: str = Field(..., max_length=128, pattern=r"^[a-zA-Z0-9_\-\./]+$")
    protocol_id: str | None = Field(None, max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$")
    split: str | None = Field(None, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
    sample_size_mode: str = Field("smoke", pattern=r"^(smoke|pilot|standard|full)$")
    sample_count: int | None = Field(
        None, ge=1, le=10000, validation_alias=AliasChoices("sample_count", "samples")
    )
    seed: int = Field(42, ge=1, le=2147483647)
    is_private: bool = True


class BenchmarkRunResponse(BaseModel):
    id: str
    user_id: int
    model_id: str
    dataset_id: str
    protocol_id: str
    split: str
    sample_size_mode: str
    sample_count: int
    seed: int
    status: RunStatusEnum
    is_private: bool
    cancel_requested: bool
    progress_done: int
    progress_total: int
    error_text: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedRunsResponse(BaseModel):
    items: list[BenchmarkRunResponse]
    total: int
    limit: int
    offset: int


class RunStatusResponse(BaseModel):
    id: str
    status: RunStatusEnum
    progress_done: int
    progress_total: int
    cancel_requested: bool
    error_text: str | None = None


class RunResultsResponse(BaseModel):
    run_id: str
    status: RunStatusEnum
    metrics: dict[str, float]
    hardware_metadata: dict[str, Any] | None = None
    sample_selection: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class PaginatedPredictionsResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
