"""Benchmark execution engine and public entry point.

Authoritative source: docs/ARCHITECTURE.md §3, §4, §6, §11, §12.

Public Integration Contract:
    run_benchmark(
        run_id: str,
        model_id: str,
        dataset_id: str,
        split: str,
        sample_count: str | int | None,
        seed: int,
        protocol_id: str | None = None,
        artifacts_dir: str | Path | None = None,
        device: str = "cuda",
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        on_model_loaded: Callable[[], None] | None = None,
    ) -> dict[str, float]
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from benchmark.core.artifacts import DefaultArtifactStore
from benchmark.core.hardware import capture_hardware_info
from benchmark.core.metrics import DefaultMetricsCollector
from benchmark.core.prompt import DefaultPromptBuilder
from benchmark.core.registry import ConfigRegistry
from benchmark.core.sampling import resolve_sample_count
from benchmark.core.types import (
    BenchmarkRunner,
    NormalizedSample,
    ParseResult,
    ParseStatus,
    PredictionRecord,
)
from benchmark.evaluators.legalbench import parse_legal_output
from benchmark.evaluators.sciq import parse_sciq_output
from benchmark.evaluators.wdc_pave import parse_wdc_output


def _parse_sample_prediction(
    dataset_id: str, raw_output: str, sample: NormalizedSample
) -> ParseResult:
    """Dispatches raw output to suite-specific parser."""
    d_id = dataset_id.lower()
    if d_id == "sciq":
        options = sample.input_payload.get("options", {})
        return parse_sciq_output(raw_output, options)
    if "wdc" in d_id:
        return parse_wdc_output(raw_output)
    if "legalbench" in d_id:
        return parse_legal_output(raw_output)

    # General / IFEval / FaithEval: raw output string preserved
    return ParseResult(
        raw_output=raw_output,
        parsed_output=raw_output.strip(),
        parse_status=ParseStatus.SUCCESS,
        parse_error=None,
    )


class DefaultBenchmarkRunner(BenchmarkRunner):
    """Executes single-model benchmark lifecycle with cancellation polling and atomic persistence."""

    def __init__(
        self,
        registry: ConfigRegistry | None = None,
        artifacts_dir: str | Path = "artifacts",
    ) -> None:
        self.registry = registry or ConfigRegistry()
        self.artifact_store = DefaultArtifactStore(artifacts_dir)

    def run(
        self,
        run_id: str,
        model_id: str,
        dataset_id: str,
        split: str,
        sample_count: str | int | None,
        seed: int,
        protocol_id: str | None = None,
        device: str = "cuda",
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        on_model_loaded: Callable[[], None] | None = None,
    ) -> dict[str, float]:
        """Execute benchmark run end-to-end."""
        # 1. Capture and persist hardware info
        hardware_info = capture_hardware_info()
        self.artifact_store.save_json(run_id, "hardware.json", hardware_info)

        # 2. Lookup configurations
        model_cfg = self.registry.get_model_config(model_id)
        dataset_cfg = self.registry.get_dataset_config(dataset_id)
        canon_dataset_id = dataset_cfg.get("id", dataset_id)

        proto_id = protocol_id or dataset_cfg.get("default_protocol_id")
        protocol_cfg = self.registry.get_protocol_config(proto_id)
        evaluator_key = dataset_cfg.get("evaluator_key", "")
        evaluator = self.registry.get_evaluator(evaluator_key)

        # 3. Load dataset samples and persist run configuration
        dataset_adapter = self.registry.get_dataset_adapter(canon_dataset_id, protocol_id=proto_id)
        count = resolve_sample_count(sample_count, dataset_cfg)
        samples = dataset_adapter.load_samples(split=split, limit=count, seed=seed)

        shortfall = max(0, count - len(samples)) if count is not None else 0
        shortfall_report = {
            "status": "shortfall" if shortfall > 0 else "ok",
            "requested_samples": count if count is not None else len(samples),
            "actual_samples": len(samples),
            "shortfall": shortfall,
        }
        if shortfall > 0:
            import logging
            logging.getLogger("benchmark.runner").warning(
                f"Requested {count} samples but only {len(samples)} eligible. Shortfall: {shortfall}"
            )

        run_config: dict[str, Any] = {
            "run_id": run_id,
            "model_id": model_id,
            "dataset_id": canon_dataset_id,
            "split": split,
            "sample_count": sample_count,
            "seed": seed,
            "protocol_id": proto_id,
            "device": device,
            "requested_samples": count,
            "actual_samples": len(samples),
            "shortfall": shortfall,
            "shortfall_report": shortfall_report,
            "selected_sample_ids": [s.sample_id for s in samples],
            "model_config": model_cfg,
            "dataset_config": dataset_cfg,
            "protocol_config": protocol_cfg,
        }
        self.artifact_store.save_json(run_id, "run_config.json", run_config)
        self.artifact_store.append_log(
            run_id, f"Initialized run {run_id} for model={model_id}, dataset={canon_dataset_id}, samples={len(samples)}"
        )

        if not samples:
            empty_metrics = {"sample_count": 0.0}
            self.artifact_store.save_json(run_id, "metrics.json", empty_metrics)
            return empty_metrics

        # 4. Load Model and Tokenizer
        model_adapter = self.registry.get_model_adapter(model_id)
        self.artifact_store.append_log(run_id, f"Loading model weights into device={device}...")
        model_adapter.load(device=device)

        if on_model_loaded is not None:
            on_model_loaded()

        # 5. Initialize PromptBuilder and MetricsCollector
        prompt_template = protocol_cfg.get("prompt_template", "{text}")
        add_gen_prompt = bool(model_cfg.get("add_generation_prompt", True))
        prompt_builder = DefaultPromptBuilder(
            prompt_template=prompt_template,
            tokenizer=getattr(model_adapter, "tokenizer", None),
            add_generation_prompt=add_gen_prompt,
        )

        metrics_collector = DefaultMetricsCollector()
        metrics_collector.set_model_load_time_s(model_adapter.load_time_s)

        # 6. Warmup Pass (1 sample inference, discard from latency metrics per ARCHITECTURE §4.2)
        try:
            warmup_sample = samples[0]
            w_prompt, _ = prompt_builder.build_prompt(warmup_sample)
            w_out = model_adapter.generate(w_prompt)
            metrics_collector.record_inference(
                w_out.latency_ms, w_out.input_tokens, w_out.output_tokens, is_warmup=True
            )
            self.artifact_store.append_log(
                run_id, f"Warmup completed: latency={w_out.latency_ms}ms, in_tokens={w_out.input_tokens}"
            )
        except Exception as e:
            self.artifact_store.append_log(run_id, f"Warmup failed (non-fatal): {e}")

        # 7. Sample Inference Loop
        predictions: list[PredictionRecord] = []
        total_samples = len(samples)

        try:
            for idx, sample in enumerate(samples):
                # Cancellation check between samples
                if cancel_check is not None and cancel_check():
                    self.artifact_store.append_log(run_id, f"Cancellation requested at sample {idx}/{total_samples}")
                    break

                prompt_text, prompt_hash = prompt_builder.build_prompt(sample)
                gen_out = model_adapter.generate(prompt_text)

                metrics_collector.record_inference(
                    gen_out.latency_ms,
                    gen_out.input_tokens,
                    gen_out.output_tokens,
                    is_warmup=False,
                )

                # Parse model response without discarding unparseable outputs
                parse_res = _parse_sample_prediction(canon_dataset_id, gen_out.raw_text, sample)

                record = PredictionRecord(
                    sample_id=sample.sample_id,
                    model_id=model_id,
                    model_revision=model_adapter.revision,
                    protocol_version=protocol_cfg.get("version", "1.0.0"),
                    prompt_hash=prompt_hash,
                    raw_output=gen_out.raw_text,
                    parsed_output=parse_res.parsed_output,
                    parse_status=str(parse_res.parse_status),
                    parse_error=parse_res.parse_error,
                    input_tokens=gen_out.input_tokens,
                    output_tokens=gen_out.output_tokens,
                    latency_ms=gen_out.latency_ms,
                    error=gen_out.error,
                )
                predictions.append(record)

                if progress_callback is not None:
                    progress_callback(idx + 1, total_samples)
        finally:
            # Always unload model and free GPU memory completely per ARCHITECTURE contract
            self.artifact_store.append_log(run_id, "Unloading model and clearing GPU VRAM...")
            model_adapter.unload()

        # 8. Evaluation and Persistence
        eval_metrics = evaluator.evaluate(predictions, samples)
        perf_metrics = metrics_collector.compute_summary()
        final_metrics = {**eval_metrics, **perf_metrics}

        self.artifact_store.save_predictions_jsonl(run_id, predictions)
        self.artifact_store.save_json(run_id, "metrics.json", final_metrics)
        self.artifact_store.append_log(run_id, f"Run completed successfully: {final_metrics}")

        return final_metrics


def run_benchmark(
    run_id: str,
    model_id: str,
    dataset_id: str,
    split: str,
    sample_count: str | int | None,
    seed: int,
    protocol_id: str | None = None,
    artifacts_dir: str | Path | None = None,
    device: str = "cuda",
    progress_callback: Callable[[int, int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    on_model_loaded: Callable[[], None] | None = None,
) -> dict[str, float]:
    """Public entry point for Rapier Bench benchmark runs.

    Integration contract with app.jobs.runner. Returns aggregated metrics dictionary.
    """
    artifacts_path = artifacts_dir or "artifacts"
    runner = DefaultBenchmarkRunner(artifacts_dir=artifacts_path)
    return runner.run(
        run_id=run_id,
        model_id=model_id,
        dataset_id=dataset_id,
        split=split,
        sample_count=sample_count,
        seed=seed,
        protocol_id=protocol_id,
        device=device,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
        on_model_loaded=on_model_loaded,
    )
