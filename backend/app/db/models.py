import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RunStatusEnum(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    runs: Mapped[list["BenchmarkRun"]] = relationship(back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA-256 of session token
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")


class ModelDefinition(Base):
    __tablename__ = "model_definitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "lfm2.5-350m"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    hf_id: Mapped[str] = mapped_column(String(255), nullable=False)
    revision: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[int] = mapped_column(Integer, nullable=False)
    context_length: Mapped[int] = mapped_column(Integer, nullable=False)
    torch_dtype: Mapped[str] = mapped_column(String(32), default="bfloat16")
    vram_weight_gb: Mapped[float] = mapped_column(Float, nullable=False)
    trust_remote_code: Mapped[bool] = mapped_column(Boolean, default=False)
    license: Mapped[str] = mapped_column(String(64), nullable=False)


class DatasetDefinition(Base):
    __tablename__ = "dataset_definitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "sciq"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    hf_id: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    default_split: Mapped[str] = mapped_column(String(32), default="test")
    evaluator_key: Mapped[str] = mapped_column(String(64), nullable=False)


class BenchmarkProtocol(Base):
    __tablename__ = "benchmark_protocols"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "sciq_evidence_grounded"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_definitions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer_format: Mapped[str] = mapped_column(String(64), nullable=False)


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID4
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    model_id: Mapped[str] = mapped_column(
        ForeignKey("model_definitions.id"), index=True, nullable=False
    )
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_definitions.id"), index=True, nullable=False
    )
    protocol_id: Mapped[str] = mapped_column(ForeignKey("benchmark_protocols.id"), nullable=False)
    split: Mapped[str] = mapped_column(String(32), default="test")
    sample_size_mode: Mapped[str] = mapped_column(String(32), default="smoke")
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, default=42)
    status: Mapped[RunStatusEnum] = mapped_column(
        Enum(RunStatusEnum), default=RunStatusEnum.QUEUED, index=True
    )
    is_private: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_selection: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    generation_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    hardware_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="runs")
    metrics: Mapped[list["BenchmarkMetric"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class BenchmarkMetric(Base):
    __tablename__ = "benchmark_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    metric_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)

    run: Mapped["BenchmarkRun"] = relationship(back_populates="metrics")
    __table_args__ = (Index("ix_run_metric", "run_id", "metric_name"),)


class PredictionIndex(Base):
    __tablename__ = "prediction_indices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sample_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    artifact_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # "predictions", "metrics", "logs"
    relative_path: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    run: Mapped["BenchmarkRun"] = relationship(back_populates="artifacts")


class RecommendationPreference(Base):
    __tablename__ = "recommendation_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    weight_quality: Mapped[float] = mapped_column(Float, default=0.5)
    weight_latency: Mapped[float] = mapped_column(Float, default=0.3)
    weight_vram: Mapped[float] = mapped_column(Float, default=0.2)
    max_vram_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)


class GpuLock(Base):
    __tablename__ = "gpu_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Always 1
    holder_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
