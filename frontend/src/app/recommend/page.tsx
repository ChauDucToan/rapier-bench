"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { formatLatency, formatVram } from "@/lib/formatters";
import { LoadingState } from "@/components/StatusState";
import type { RecommendationResponse } from "@/types/api";

const DOMAINS = [
  { id: "education", label: "Education (SciQ)", task: "multiple_choice" },
  { id: "ecommerce", label: "E-Commerce (WDC-PAVE)", task: "attribute_value_extraction" },
  { id: "legal", label: "Legal (Contract NLI)", task: "binary_classification" },
  { id: "general", label: "General Instruction (IFEval)", task: "instruction_following" },
  { id: "contextual_faithfulness", label: "Contextual Faithfulness (FaithEval)", task: "contextual_faithfulness" },
];

export default function RecommendPage() {
  const [selectedDomain, setSelectedDomain] = useState("education");
  const [taskType, setTaskType] = useState("multiple_choice");

  // Constraints
  const [maxVram, setMaxVram] = useState<string>("");
  const [maxLatency, setMaxLatency] = useState<string>("");
  const [minQuality, setMinQuality] = useState<string>("");

  // Weights (sliders from 0 to 100)
  const [qualityWeight, setQualityWeight] = useState<number>(50);
  const [latencyWeight, setLatencyWeight] = useState<number>(30);
  const [vramWeight, setVramWeight] = useState<number>(20);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RecommendationResponse | null>(null);

  // Normalized weights computation for display
  const totalWeight = qualityWeight + latencyWeight + vramWeight;
  const normQ = totalWeight > 0 ? (qualityWeight / totalWeight).toFixed(2) : "0.00";
  const normL = totalWeight > 0 ? (latencyWeight / totalWeight).toFixed(2) : "0.00";
  const normV = totalWeight > 0 ? (vramWeight / totalWeight).toFixed(2) : "0.00";

  function handleDomainChange(newDom: string) {
    setSelectedDomain(newDom);
    const found = DOMAINS.find((d) => d.id === newDom);
    if (found) {
      setTaskType(found.task);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (totalWeight <= 0) {
      setError("At least one weight slider must be greater than zero.");
      return;
    }

    setLoading(true);
    try {
      const response = await api.recommendations.create({
        domain: selectedDomain,
        task_type: taskType || undefined,
        constraints: {
          max_vram_gb: maxVram ? parseFloat(maxVram) : undefined,
          max_latency_ms: maxLatency ? parseFloat(maxLatency) : undefined,
          min_quality: minQuality ? parseFloat(minQuality) : undefined,
        },
        weights: {
          quality: qualityWeight / (totalWeight || 1),
          latency: latencyWeight / (totalWeight || 1),
          vram: vramWeight / (totalWeight || 1),
        },
      });

      setResult(response);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to generate model recommendation",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="py-6 space-y-8 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Explainable Model Recommender
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Rank small language models deterministically using empirical multi-objective optimization across quality, latency, and VRAM.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6" noValidate>
        {/* Domain & Task selection */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-4">
          <h2 className="text-sm font-semibold text-white">
            1. Target Domain & Task Type
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="domain-select"
                className="block text-xs font-medium text-zinc-300"
              >
                Domain
              </label>
              <select
                id="domain-select"
                value={selectedDomain}
                onChange={(e) => handleDomainChange(e.target.value)}
                className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {DOMAINS.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="task-input"
                className="block text-xs font-medium text-zinc-300"
              >
                Task Type
              </label>
              <input
                id="task-input"
                type="text"
                value={taskType}
                onChange={(e) => setTaskType(e.target.value)}
                className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>
        </div>

        {/* Hardware Constraints */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-4">
          <h2 className="text-sm font-semibold text-white">
            2. Hard Deployment Constraints (Optional)
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label
                htmlFor="max-vram"
                className="block text-xs font-medium text-zinc-300"
              >
                Max VRAM (GB)
              </label>
              <input
                id="max-vram"
                type="number"
                step="0.1"
                min="0"
                placeholder="e.g. 2.0"
                value={maxVram}
                onChange={(e) => setMaxVram(e.target.value)}
                className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-white placeholder-zinc-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label
                htmlFor="max-latency"
                className="block text-xs font-medium text-zinc-300"
              >
                Max Latency (ms)
              </label>
              <input
                id="max-latency"
                type="number"
                step="1"
                min="0"
                placeholder="e.g. 150"
                value={maxLatency}
                onChange={(e) => setMaxLatency(e.target.value)}
                className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-white placeholder-zinc-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label
                htmlFor="min-quality"
                className="block text-xs font-medium text-zinc-300"
              >
                Min Quality (0.00–1.00)
              </label>
              <input
                id="min-quality"
                type="number"
                step="0.05"
                min="0"
                max="1"
                placeholder="e.g. 0.50"
                value={minQuality}
                onChange={(e) => setMinQuality(e.target.value)}
                className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-white placeholder-zinc-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>
        </div>

        {/* Priority Weights */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">
              3. Objective Trade-Off Weights
            </h2>
            <span className="text-xs text-zinc-400 font-mono">
              Normalized: Q={normQ} | L={normL} | V={normV}
            </span>
          </div>

          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-xs text-zinc-300">
                <label htmlFor="quality-slider">Quality Weight ({normQ})</label>
                <span className="font-mono text-zinc-400">{qualityWeight}%</span>
              </div>
              <input
                id="quality-slider"
                type="range"
                min="0"
                max="100"
                value={qualityWeight}
                onChange={(e) => setQualityWeight(parseInt(e.target.value, 10))}
                className="mt-1.5 w-full accent-indigo-500"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs text-zinc-300">
                <label htmlFor="latency-slider">Speed / Latency Weight ({normL})</label>
                <span className="font-mono text-zinc-400">{latencyWeight}%</span>
              </div>
              <input
                id="latency-slider"
                type="range"
                min="0"
                max="100"
                value={latencyWeight}
                onChange={(e) => setLatencyWeight(parseInt(e.target.value, 10))}
                className="mt-1.5 w-full accent-indigo-500"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs text-zinc-300">
                <label htmlFor="vram-slider">VRAM Efficiency Weight ({normV})</label>
                <span className="font-mono text-zinc-400">{vramWeight}%</span>
              </div>
              <input
                id="vram-slider"
                type="range"
                min="0"
                max="100"
                value={vramWeight}
                onChange={(e) => setVramWeight(parseInt(e.target.value, 10))}
                className="mt-1.5 w-full accent-indigo-500"
              />
            </div>
          </div>
        </div>

        {error && (
          <div
            role="alert"
            aria-live="polite"
            className="rounded-md border border-red-800/60 bg-red-950/40 p-3 text-xs text-red-300"
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Optimizing Model Recommendations..." : "Generate Recommendation"}
        </button>
      </form>

      {loading && (
        <LoadingState message="Ranking candidate models against empirical telemetry..." />
      )}

      {result && (
        <div className="space-y-6 pt-4">
          {/* Insufficient sample state */}
          {result.status === "insufficient_sample" ? (
            <div
              role="status"
              aria-live="polite"
              className="rounded-xl border border-amber-800/60 bg-amber-950/30 p-6 text-amber-200 space-y-3"
            >
              <h3 className="text-base font-semibold text-amber-100">
                Insufficient Sample Size (§10.2 Guard)
              </h3>
              <p className="text-sm text-amber-300">
                {result.explanation ||
                  "Fewer than 3 unique models have completed evaluation runs for this domain/task. No synthetic rankings are generated."}
              </p>
              {result.limitations && result.limitations.length > 0 && (
                <ul className="list-disc list-inside text-xs text-amber-400 space-y-1 pt-1">
                  {result.limitations.map((lim, idx) => (
                    <li key={idx}>{lim}</li>
                  ))}
                </ul>
              )}
              <div className="pt-2">
                <Link
                  href="/benchmarks/new"
                  className="rounded bg-amber-900/60 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-amber-800"
                >
                  Run More Benchmarks
                </Link>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Explanation & Weights Used */}
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-2">
                <h3 className="text-sm font-semibold text-white">
                  Optimization Summary
                </h3>
                <p className="text-xs text-zinc-300 leading-relaxed">
                  {result.explanation}
                </p>
              </div>

              {/* Ranked Candidate List */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-white">
                  Ranked Candidates ({result.recommendations.length} eligible)
                </h3>
                <div className="space-y-3">
                  {result.recommendations.map((cand, idx) => (
                    <div
                      key={cand.model_id}
                      className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-4"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-zinc-800 pb-3">
                        <div className="flex items-center gap-3">
                          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-900/80 text-xs font-bold text-indigo-200">
                            #{idx + 1}
                          </span>
                          <div>
                            <div className="font-semibold text-white">
                              {cand.model_name || cand.model_id}
                            </div>
                            <div className="font-mono text-xs text-zinc-500">
                              {cand.model_id}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <div className="text-right">
                            <span className="text-[10px] text-zinc-400 uppercase tracking-wider">
                              Composite Score
                            </span>
                            <div className="font-mono text-lg font-bold text-indigo-400">
                              {(cand.composite_score * 100).toFixed(1)}
                            </div>
                          </div>
                          <Link
                            href={`/benchmarks/${cand.run_id}`}
                            className="rounded border border-zinc-700 bg-zinc-800 px-2.5 py-1 text-xs text-zinc-300 hover:bg-zinc-700"
                          >
                            View Run
                          </Link>
                        </div>
                      </div>

                      {/* Score Breakdown */}
                      <dl className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
                        <div className="rounded border border-zinc-800 bg-zinc-950/60 p-3">
                          <dt className="text-zinc-500">Quality (Primary)</dt>
                          <dd className="mt-1 font-mono text-sm font-bold text-emerald-400">
                            {(cand.quality_score * 100).toFixed(1)}%
                          </dd>
                          <span className="text-[10px] text-zinc-600 font-mono">
                            Norm: {cand.normalized_quality.toFixed(2)}
                          </span>
                        </div>

                        <div className="rounded border border-zinc-800 bg-zinc-950/60 p-3">
                          <dt className="text-zinc-500">Latency</dt>
                          <dd className="mt-1 font-mono text-sm font-bold text-white">
                            {formatLatency(cand.latency_ms)}
                          </dd>
                          <span className="text-[10px] text-zinc-600 font-mono">
                            {cand.normalized_latency !== null && cand.normalized_latency !== undefined
                              ? `Norm: ${cand.normalized_latency.toFixed(2)}`
                              : "Not measured"}
                          </span>
                        </div>

                        <div className="rounded border border-zinc-800 bg-zinc-950/60 p-3">
                          <dt className="text-zinc-500">VRAM Footprint (est.)</dt>
                          <dd className="mt-1 font-mono text-sm font-bold text-white">
                            {formatVram(cand.vram_gb)}
                          </dd>
                          <span className="text-[10px] text-zinc-600 font-mono">
                            Model-weight estimate; not measured peak
                          </span>
                        </div>
                      </dl>
                    </div>
                  ))}
                </div>
              </div>

              {/* Trade-offs & Limitations */}
              {result.limitations && result.limitations.length > 0 && (
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Known Limitations & Constraints
                  </h3>
                  <ul className="list-disc list-inside text-xs text-zinc-400 space-y-1">
                    {result.limitations.map((lim, i) => (
                      <li key={i}>{lim}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
