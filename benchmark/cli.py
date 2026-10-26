"""Command-line interface for benchmark execution.

Authoritative source: docs/ARCHITECTURE.md Section 12.2.
"""

import argparse
import sys
import uuid

from benchmark.core.prompt import DefaultPromptBuilder
from benchmark.core.registry import ConfigRegistry
from benchmark.core.runner import run_benchmark
from benchmark.core.sampling import resolve_sample_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="benchmark.cli", description="Rapier Bench Execution CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run benchmark suite")
    run_parser.add_argument("--model", required=True, help="Model ID or HF repo ID")
    run_parser.add_argument("--dataset", required=True, help="Dataset ID")
    run_parser.add_argument("--split", default=None, help="Dataset split (default: dataset default_split)")
    run_parser.add_argument("--protocol", default=None, help="Benchmark protocol ID")
    run_parser.add_argument("--samples", default="smoke", help="Sample count or mode (smoke, pilot, standard, full, or int)")
    run_parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed (default: 42)")
    run_parser.add_argument("--dry-run", action="store_true", help="Select samples, render prompts, print hashes and exit 0 without loading weights")
    run_parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"], help="Inference device (cuda or cpu)")
    run_parser.add_argument("--output-dir", default="artifacts", help="Artifacts output directory")

    return parser


def handle_dry_run(args: argparse.Namespace) -> int:
    """Execute dry-run without loading weights or touching the GPU."""
    registry = ConfigRegistry()
    model_cfg = registry.get_model_config(args.model)
    dataset_cfg = registry.get_dataset_config(args.dataset)
    canon_dataset_id = dataset_cfg.get("id", args.dataset)
    args.split = args.split or dataset_cfg.get("default_split", "test")

    protocol_id = args.protocol or dataset_cfg.get("default_protocol_id")
    protocol_cfg = registry.get_protocol_config(protocol_id)

    # Load dataset samples
    dataset_adapter = registry.get_dataset_adapter(canon_dataset_id, protocol_id=protocol_id)
    count = resolve_sample_count(args.samples, dataset_cfg)
    samples = dataset_adapter.load_samples(split=args.split, limit=count, seed=args.seed)

    prompt_template = protocol_cfg.get("prompt_template", "{text}")
    # Dry run has no loaded model weights; instantiate prompt builder without tokenizer
    builder = DefaultPromptBuilder(prompt_template=prompt_template)

    print("--- Rapier Bench Dry Run ---")
    print(f"Model ID: {model_cfg.get('id')} ({model_cfg.get('hf_id')})")
    print(f"Dataset: {canon_dataset_id} (Split: {args.split})")
    print(f"Protocol: {protocol_id}")
    print(f"Requested count: {count}, Selected: {len(samples)}")
    print("--------------------------------------------------")

    for idx, sample in enumerate(samples, 1):
        prompt_text, p_hash = builder.build_prompt(sample)
        print(f"[{idx:03d}] ID: {sample.sample_id} | Hash: {p_hash}")

    print("--------------------------------------------------")
    print("Dry run completed successfully (0 weights loaded, 0 GPU operations).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        if args.dry_run:
            return handle_dry_run(args)

        # Resolve dataset default split for non-dry runs (same rule as dry-run handler)
        dataset_cfg = ConfigRegistry().get_dataset_config(args.dataset)
        args.split = args.split or dataset_cfg.get("default_split", "test")

        run_id = f"cli_{uuid.uuid4().hex[:12]}"
        print(f"Starting benchmark run {run_id} on device={args.device}...")
        metrics = run_benchmark(
            run_id=run_id,
            model_id=args.model,
            dataset_id=args.dataset,
            split=args.split,
            sample_count=args.samples,
            seed=args.seed,
            protocol_id=args.protocol,
            artifacts_dir=args.output_dir,
            device=args.device,
            progress_callback=lambda done, total: print(f"Progress: {done}/{total} samples completed"),
        )
        print("Run finished. Metrics:")
        for k, v in metrics.items():
            print(f"  {k}: {v}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
