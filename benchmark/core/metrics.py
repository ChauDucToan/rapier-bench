"""Inference metrics collector and statistical aggregation.

Authoritative source: docs/ARCHITECTURE.md Section 3 and Section 4.
"""

import math
import statistics
from typing import Any

from benchmark.core.types import MetricsCollector


class DefaultMetricsCollector(MetricsCollector):
    """Accumulates inference timings and token totals, computing summary statistics."""

    def __init__(self) -> None:
        self.latencies_ms: list[float] = []
        self.input_tokens: list[int] = []
        self.output_tokens: list[int] = []
        self.warmup_latencies_ms: list[float] = []
        self.model_load_time_s: float = 0.0

    def set_model_load_time_s(self, load_time_s: float) -> None:
        """Record model load time separately."""
        self.model_load_time_s = float(load_time_s)

    def record_inference(
        self, latency_ms: float, in_tokens: int, out_tokens: int, is_warmup: bool = False
    ) -> None:
        """Record inference timing and token count. Warmup passes are kept separate."""
        if is_warmup:
            self.warmup_latencies_ms.append(float(latency_ms))
            return
        self.latencies_ms.append(float(latency_ms))
        self.input_tokens.append(int(in_tokens))
        self.output_tokens.append(int(out_tokens))

    def compute_summary(self) -> dict[str, float]:
        """Compute mean, median, p50, p95, throughput, and token totals."""
        n = len(self.latencies_ms)
        if n == 0:
            return {
                "latency_ms_mean": 0.0,
                "latency_ms_median": 0.0,
                "latency_ms_p50": 0.0,
                "latency_ms_p95": 0.0,
                "tokens_per_sec": 0.0,
                "total_input_tokens": 0.0,
                "total_output_tokens": 0.0,
                "sample_count": 0.0,
                "model_load_time_s": self.model_load_time_s,
            }

        sorted_latencies = sorted(self.latencies_ms)
        mean_latency = statistics.mean(sorted_latencies)
        median_latency = statistics.median(sorted_latencies)

        # p95 computation
        # ponytail: standard rank-based percentile for small/medium sample counts
        p95_idx = min(int(math.ceil(0.95 * n)) - 1, n - 1)
        p95_latency = sorted_latencies[max(0, p95_idx)]

        total_out = sum(self.output_tokens)
        total_time_s = sum(sorted_latencies) / 1000.0
        tokens_per_sec = (total_out / total_time_s) if total_time_s > 0 else 0.0

        return {
            "latency_ms_mean": round(mean_latency, 2),
            "latency_ms_median": round(median_latency, 2),
            "latency_ms_p50": round(median_latency, 2),
            "latency_ms_p95": round(p95_latency, 2),
            "tokens_per_sec": round(tokens_per_sec, 2),
            "total_input_tokens": float(sum(self.input_tokens)),
            "total_output_tokens": float(total_out),
            "sample_count": float(n),
            "model_load_time_s": round(self.model_load_time_s, 2),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.compute_summary()
