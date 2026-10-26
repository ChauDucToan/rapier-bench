"""Hugging Face causal language model adapter."""

import gc
import time
from typing import Any

from benchmark.core.types import GenerationOutput, ModelAdapter


class HFCausalModelAdapter(ModelAdapter):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.tokenizer = None
        self.model = None
        self.device = "cuda"
        self.load_time_s = 0.0
        self.revision = str(config.get("revision", "main"))

    def load(self, device: str = "cuda") -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but torch.cuda.is_available() is False; request CPU explicitly")
        self.device = device
        hf_id = self.config["hf_id"]
        revision = self.config.get("revision")
        trust_remote_code = self.config.get("trust_remote_code", False)
        self.revision = str(revision or "main")
        self.tokenizer = AutoTokenizer.from_pretrained(
            hf_id, revision=revision, trust_remote_code=trust_remote_code
        )
        dtype_name = self.config.get("torch_dtype")
        torch_dtype = getattr(torch, dtype_name) if dtype_name else None
        kwargs = {
            "revision": revision,
            "torch_dtype": torch_dtype,
            "trust_remote_code": trust_remote_code,
        }
        attn_implementation = self.config.get("attn_implementation")
        if attn_implementation:
            kwargs["attn_implementation"] = attn_implementation
        started = time.perf_counter()
        self.model = AutoModelForCausalLM.from_pretrained(hf_id, **kwargs)
        self.model.to(device)
        self.load_time_s = time.perf_counter() - started
        self.model.eval()

    def generate(
        self, prompt: str, generation_config: dict[str, Any] | None = None
    ) -> GenerationOutput:
        import torch

        input_tokens = output_tokens = 0
        started = time.perf_counter()
        try:
            if self.model is None or self.tokenizer is None:
                raise RuntimeError("Model is not loaded")
            encoded = self.tokenizer(
                prompt,
                return_tensors="pt",
                return_token_type_ids=False,
                add_special_tokens=False,
            ).to(self.device)
            input_ids = encoded["input_ids"]
            input_tokens = input_ids.shape[-1]
            if self.device.startswith("cuda"):
                torch.cuda.synchronize()
            started = time.perf_counter()
            config = {**self.config.get("generation_defaults", {}), **(generation_config or {})}
            with torch.inference_mode():
                output_ids = self.model.generate(**encoded, **config)
            if self.device.startswith("cuda"):
                torch.cuda.synchronize()
            latency_ms = (time.perf_counter() - started) * 1000
            output_tokens = output_ids.shape[-1] - input_tokens
            raw_text = self.tokenizer.decode(output_ids[0, input_tokens:], skip_special_tokens=True)
            return GenerationOutput(
                raw_text=raw_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                model_id=self.config["id"],
                model_revision=self.revision,
            )
        except Exception as exc:
            return GenerationOutput(
                raw_text="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=0.0,
                model_id=self.config["id"],
                model_revision=self.revision,
                error=str(exc),
            )

    def unload(self) -> None:
        import torch

        self.model = None
        self.tokenizer = None
        gc.collect()
        if self.device.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.empty_cache()

    @property
    def is_loaded(self) -> bool:
        return self.model is not None and self.tokenizer is not None
