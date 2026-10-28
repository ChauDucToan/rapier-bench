"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { EmptyState, ErrorState, LoadingState } from "@/components/StatusState";
import type { DatasetResponse } from "@/types/api";

const DOMAIN_OPTIONS = [
  { value: "", label: "All Domains" },
  { value: "education", label: "Education" },
  { value: "ecommerce", label: "E-Commerce" },
  { value: "legal", label: "Legal" },
  { value: "general", label: "General" },
  { value: "contextual_faithfulness", label: "Faithfulness" },
];

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetResponse[]>([]);
  const [domainFilter, setDomainFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    api.datasets
      .list({ domain: domainFilter || undefined, limit: 100 })
      .then((res) => {
        if (!ignore) {
          setDatasets(res);
          setError(null);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Failed to load datasets");
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
            Dataset Suites
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Registered evaluation datasets with their domains, task types, and
            evaluator keys.
          </p>
        </div>
        <Link
          href="/benchmarks/new"
          className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500"
        >
          Run a Benchmark
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
        <label
          htmlFor="domain-filter"
          className="block text-xs font-medium text-zinc-400"
        >
          Domain
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
        <LoadingState message="Loading dataset suites..." />
      ) : error ? (
        <ErrorState title="Failed to load datasets" message={error} />
      ) : datasets.length === 0 ? (
        <EmptyState
          title="No datasets found"
          message={
            domainFilter
              ? "No dataset suites are registered for this domain."
              : "The dataset catalog is empty. Datasets are seeded from configs/datasets.yaml at API startup."
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {datasets.map((d) => (
            <div
              key={d.id}
              className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-white">{d.name}</h2>
                  <p className="font-mono text-xs text-zinc-500">{d.id}</p>
                </div>
                <span className="inline-flex shrink-0 items-center rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-300">
                  {d.domain}
                </span>
              </div>

              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                <div>
                  <dt className="text-zinc-500">Task Type</dt>
                  <dd className="font-mono text-zinc-200">{d.task_type}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Default Split</dt>
                  <dd className="font-mono text-zinc-200">{d.default_split}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Evaluator</dt>
                  <dd className="font-mono text-zinc-200">{d.evaluator_key}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Source</dt>
                  <dd className="truncate font-mono text-xs text-indigo-400" title={d.hf_id}>
                    {d.hf_id}
                  </dd>
                </div>
              </dl>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
