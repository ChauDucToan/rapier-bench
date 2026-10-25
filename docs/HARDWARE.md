# Hardware Benchmark Specification (RTX 3050 Laptop, 4 GiB)

Single-machine throughput and latency benchmarking protocol for local GPU inference. Distinct from quality evaluation: measures compute efficiency only.

## 1. Principles & Hard Constraints

- **No Leaderboard Claims**: Measures single-machine hardware latency. Numbers MUST NOT be compared across different hardware rigs or submitted to competitive leaderboards.
- **No Quality Metrics**: Throughput benchmarks strictly measure execution speed (tok/s, ms/tok). Do not mix with accuracy, perplexity, or quality benchmark scores.
- **One GPU Job at a Time**: Strict sequential exclusivity. Exactly one GPU process may run during benchmarking. No background GPU tasks, concurrent inference processes, or UI GPU loads.

## 2. Measurement Targets & Metrics

- **Warm Latency Per Token**: Time per generated token in steady-state decoding (ms/token).
- **Decode Throughput**: Output tokens generated per second (`tokens/sec`).
- **Prefill vs. Decode Split**:
  - `model.generate()` executes prompt prefill and autoregressive token generation in a single opaque call; it CANNOT isolate prefill from decode time.
  - Prefill vs. decode separation REQUIRES either:
    1. Logits-level manual decoding loop (`model(input_ids)` for prompt prefill, then manual sequential forward passes per generated token), or
    2. Two-config differential measurement (measure latency at $N$ tokens generated vs. 1 token generated).
- **Peak VRAM**: Tracked via `torch.cuda.max_memory_allocated()` reset immediately prior to the timed run.

## 3. Execution & Synchronization Protocol

- **Warmup Policy**: Run at least 3–5 warmup iterations (or 16 tokens generated) before timing. Discard all warmup samples to eliminate JIT compilation, kernel caching, and memory allocation spikes.
- **CUDA Synchronization Boundaries**: GPU operations are asynchronous. Wall-clock timing MUST enforce explicit CUDA synchronization boundaries before and after timed segments:
  ```python
  torch.cuda.synchronize()
  t0 = time.perf_counter()

  # Timed inference section (prefill or token decode loop)

  torch.cuda.synchronize()
  t1 = time.perf_counter()
  ```
- **Lifecycle Cleanup**: Explicit garbage collection and cache flush after every trial:
  ```python
  del model, tokenizer
  gc.collect()
  torch.cuda.empty_cache()
  ```

## 4. Mandatory Run Metadata

Every benchmark output artifact MUST record:
1. **Device**: `NVIDIA GeForce RTX 3050 Laptop GPU` (4096 MiB total VRAM).
2. **Driver & CUDA**: Driver `580.178.04`, CUDA `13.0`.
3. **Framework Versions**: PyTorch `2.14.1+cu130`, Transformers version.
4. **Model Configuration**: Model ID, exact revision/commit hash, total parameters, weights dtype (`fp16`/`bf16`), quantization format (e.g. Q4_K_M, AWQ, None).
5. **Inference Configuration**: Batch size (`1` required on 4 GiB target), prompt context length ($L_{\text{prompt}}$), `max_new_tokens`.
6. **Performance Results**: TTFT (Time to First Token, if isolated), decode tokens/sec, total latency (s), peak VRAM (MiB).
7. **Single-Machine Hardware Disclosure**: Explicit notation that numbers are single-machine mobile GPU results and NOT comparable to server or desktop hardware.
