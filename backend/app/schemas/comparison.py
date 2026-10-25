from typing import Any

from pydantic import BaseModel, Field

from app.schemas.benchmark import BenchmarkRunResponse


class ComparisonResponse(BaseModel):
    runs: list[BenchmarkRunResponse]
    metrics_comparison: dict[str, dict[str, float]] = Field(default_factory=dict)
    diffs: dict[str, Any] = Field(default_factory=dict)
