"""Configuration loader and adapter/evaluator registry.

Authoritative source: docs/ARCHITECTURE.md Section 3 and configs/*.yaml.
"""

from pathlib import Path
from typing import Any

import yaml

from benchmark.adapters.datasets.faitheval import FaithEvalDatasetAdapter
from benchmark.adapters.datasets.ifeval import IFEvalDatasetAdapter
from benchmark.adapters.datasets.legalbench import LegalBenchDatasetAdapter
from benchmark.adapters.datasets.sciq import SciQDatasetAdapter
from benchmark.adapters.datasets.wdc_pave import WdcPaveDatasetAdapter
from benchmark.adapters.models.hf_causal import HFCausalModelAdapter
from benchmark.core.types import DatasetAdapter, Evaluator, ModelAdapter
from benchmark.evaluators.faitheval import FaithEvalEvaluator
from benchmark.evaluators.ifeval import IFEvalEvaluator
from benchmark.evaluators.legalbench import LegalBenchEvaluator
from benchmark.evaluators.sciq import SciQEvaluator
from benchmark.evaluators.wdc_pave import WdcPaveEvaluator

DEFAULT_CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / "configs"


class ConfigRegistry:
    """Loads YAML configurations from configs/ and resolves adapters and evaluators."""

    def __init__(self, configs_dir: Path | str = DEFAULT_CONFIGS_DIR) -> None:
        self.configs_dir = Path(configs_dir).resolve()
        self.models_config: dict[str, dict[str, Any]] = {}
        self.datasets_config: dict[str, dict[str, Any]] = {}
        self.protocols_config: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        """Reload all configuration files."""
        # 1. Models config
        models_file = self.configs_dir / "models.yaml"
        if models_file.exists():
            with open(models_file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or []
                self.models_config = {m["id"]: m for m in data if "id" in m}

        # 2. Datasets config
        datasets_file = self.configs_dir / "datasets.yaml"
        if datasets_file.exists():
            with open(datasets_file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or []
                self.datasets_config = {d["id"]: d for d in data if "id" in d}

        # 3. Protocols config
        protocols_dir = self.configs_dir / "protocols"
        self.protocols_config = {}
        if protocols_dir.exists():
            for p_file in protocols_dir.glob("*.yaml"):
                with open(p_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or []
                    for proto in data:
                        if isinstance(proto, dict) and "id" in proto:
                            self.protocols_config[proto["id"]] = proto

    def get_model_config(self, model_id: str) -> dict[str, Any]:
        """Lookup model config by ID, name, or HF repository ID."""
        m_id = model_id.strip()
        if m_id in self.models_config:
            return self.models_config[m_id]

        m_lower = m_id.lower()
        for k, v in self.models_config.items():
            if (
                k.lower() == m_lower
                or v.get("hf_id", "").lower() == m_lower
                or v.get("name", "").lower() == m_lower
            ):
                return v
        raise KeyError(
            f"Model '{model_id}' not found in registry. Available: {list(self.models_config.keys())}"
        )

    def get_dataset_config(self, dataset_id: str) -> dict[str, Any]:
        """Lookup dataset config by ID or alias."""
        d_id = dataset_id.strip()
        # Aliases
        if d_id == "legalbench":
            d_id = "legalbench_contract_nli"
        elif d_id == "wdc":
            d_id = "wdc_pave"

        if d_id in self.datasets_config:
            return self.datasets_config[d_id]

        d_lower = d_id.lower()
        for k, v in self.datasets_config.items():
            if (
                k.lower() == d_lower
                or v.get("hf_id", "").lower() == d_lower
                or v.get("name", "").lower() == d_lower
            ):
                return v
        raise KeyError(
            f"Dataset '{dataset_id}' not found in registry. Available: {list(self.datasets_config.keys())}"
        )

    def get_protocol_config(self, protocol_id: str) -> dict[str, Any]:
        """Lookup protocol config by protocol ID."""
        if protocol_id in self.protocols_config:
            return self.protocols_config[protocol_id]
        raise KeyError(
            f"Protocol '{protocol_id}' not found in registry. Available: {list(self.protocols_config.keys())}"
        )

    def get_model_adapter(self, model_id: str) -> ModelAdapter:
        """Instantiate ModelAdapter for model_id."""
        cfg = self.get_model_config(model_id)
        return HFCausalModelAdapter(cfg)

    def get_dataset_adapter(
        self, dataset_id: str, protocol_id: str | None = None
    ) -> DatasetAdapter:
        """Instantiate DatasetAdapter for dataset_id."""
        cfg = self.get_dataset_config(dataset_id)
        cid = cfg.get("id")

        if cid == "sciq":
            return SciQDatasetAdapter(cfg, protocol_id=protocol_id)
        if cid == "wdc_pave":
            return WdcPaveDatasetAdapter(cfg)
        if cid == "legalbench_contract_nli":
            return LegalBenchDatasetAdapter(cfg)
        if cid == "ifeval":
            return IFEvalDatasetAdapter(cfg)
        if cid == "faitheval":
            return FaithEvalDatasetAdapter(cfg)

        raise ValueError(f"No dataset adapter registered for '{cid}'")

    def get_evaluator(self, evaluator_key: str) -> Evaluator:
        """Instantiate Evaluator for evaluator_key."""
        key = evaluator_key.strip()
        evaluators = {
            "sciq_evaluator": SciQEvaluator,
            "wdc_pave_evaluator": WdcPaveEvaluator,
            "legalbench_contract_nli_evaluator": LegalBenchEvaluator,
            "ifeval_evaluator": IFEvalEvaluator,
            "faitheval_evaluator": FaithEvalEvaluator,
        }
        if key in evaluators:
            return evaluators[key]()
        raise KeyError(
            f"Evaluator '{evaluator_key}' not found. Available: {list(evaluators.keys())}"
        )

    def list_models(self) -> list[str]:
        return list(self.models_config.keys())

    def list_datasets(self) -> list[str]:
        return list(self.datasets_config.keys())

    def list_protocols(self) -> list[str]:
        return list(self.protocols_config.keys())
