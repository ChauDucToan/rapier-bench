"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatParameters, formatVram } from "@/lib/formatters";
import { EmptyState, ErrorState, LoadingState } from "@/components/StatusState";
import type { ModelResponse } from "@/types/api";

const DOMAIN_OPTIONS = [
  { value: "", label: "All Domains" },
  { value: "education", label: "Education (SciQ)" },
  { value: "ecommerce", label: "E-Commerce (WDC-PAVE)" },
  { value: "legal", label: "Legal (LegalBench)" },
  { value: "general", label: "General (IFEval)" },
  { value: "contextual_faithfulness", label: "Faithfulness (FaithEval)" },
];

export default function ModelsPage() {
  const [models, setModels] = useState<ModelResponse[]>([]);
  const [domainFilter, setDomainFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    api.models
      .list({ domain: domainFilter || undefined, limit: 100 })
      .then((res) => {
        if (!ignore) {
          setModels(res);
          setError(null);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Failed to load models");
        }
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [domainFilter]);

  return (
    <div className="py-6 space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Model Catalog
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Registered foundation models available for benchmarking. Revisions are
            pinned to exact commits for reproducibility.
          </p>
        </div>
        <Link
          href="/benchmarks/new"
          className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500"
        >
          Run a Benchmark
        </Link>
      </div>

      {/* Domain filter: models that have completed public runs in the domain */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
        <label
          htmlFor="domain-filter"
          className="block text-xs font-medium text-zinc-400"
        >
          Domain (by completed runs)
        </label>
        <select
          id="domain-filter"
          value={domainFilter}
          onChange={(e) => setDomainFilter(e.target.value)}
          className="block rounded-md border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          {DOMAIN_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {domainFilter && (
          <button
            type="button"
            onClick={() => setDomainFilter("")}
            className="rounded border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700"
          >
            Reset
          </button>
        )}
      </div>

      {loading ? (
        <LoadingState message="Loading model catalog..." />
      ) : error ? (
        <ErrorState title="Failed to load models" message={error} />
      ) : models.length === 0 ? (
        <EmptyState
          title="No models found"
          message={
            domainFilter
              ? "No models have completed public benchmark runs in this domain yet."
              : "The model catalog is empty. Models are seeded from configs/models.yaml at API startup."
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {models.map((m) => (
            <div
              key={m.id}
              className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-white">{m.name}</h2>
                  <p className="font-mono text-xs text-zinc-500">{m.id}</p>
                </div>
                <span className="inline-flex shrink-0 items-center rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-300">
                  {m.torch_dtype}
                </span>
              </div>

              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                <div>
                  <dt className="text-zinc-500">Parameters</dt>
                  <dd className="font-mono text-zinc-200">
                    {formatParameters(m.parameters)}
                  </dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Context</dt>
                  <dd className="font-mono text-zinc-200">
                    {formatParameters(m.context_length)} tokens
                  </dd>
                </div>
                <div>
                  <dt className="text-zinc-500">VRAM (est.)</dt>
                  <dd className="font-mono text-zinc-200">
                    <span
                      title="Estimated model-weight footprint from the catalog, not measured peak inference VRAM"
                    >
                      {formatVram(m.vram_weight_gb)}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt className="text-zinc-500">License</dt>
                  <dd className="text-zinc-200">{m.license}</dd>
                </div>
              </dl>

              <div className="space-y-1 border-t border-zinc-800 pt-3">
                <p className="text-[11px] text-zinc-500">
                  Hugging Face repository
                </p>
                <p className="truncate font-mono text-xs text-indigo-400">
                  {m.hf_id}
                </p>
                <p className="truncate font-mono text-[10px] text-zinc-600" title={m.revision}>
                  rev: {m.revision.slice(0, 12)}…
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
