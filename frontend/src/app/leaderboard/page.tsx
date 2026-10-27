"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  formatDate,
  formatLatency,
  formatMetricName,
  formatMetricValue,
  formatVram,
} from "@/lib/formatters";
import { EmptyState, ErrorState, LoadingState } from "@/components/StatusState";
import type { LeaderboardGroup } from "@/types/api";

const DOMAIN_OPTIONS = [
  { value: "", label: "All Domains" },
  { value: "education", label: "Education (SciQ)" },
  { value: "ecommerce", label: "E-Commerce (WDC-PAVE)" },
  { value: "legal", label: "Legal (LegalBench Contract NLI)" },
  { value: "general", label: "General (IFEval)" },
  { value: "contextual_faithfulness", label: "Contextual Faithfulness (FaithEval)" },
];

export default function LeaderboardPage() {
  const [groups, setGroups] = useState<LeaderboardGroup[]>([]);
  const [domainFilter, setDomainFilter] = useState("");
  const [taskFilter, setTaskFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    api.leaderboard
      .get({
        domain: domainFilter || undefined,
        task_type: taskFilter || undefined,
      })
      .then((res) => {
        if (!ignore) {
          setGroups(res.groups || []);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load empirical leaderboard",
          );
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [domainFilter, taskFilter]);

  function handleRetry() {
    setLoading(true);
    setError(null);
    api.leaderboard
      .get({
        domain: domainFilter || undefined,
        task_type: taskFilter || undefined,
      })
      .then((res) => {
        setGroups(res.groups || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load empirical leaderboard",
        );
        setLoading(false);
      });
  }

  return (
    <div className="py-6 space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Empirical Model Leaderboard
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Public benchmark results ranked by primary task-specific evaluation metrics.
          </p>
        </div>
        <Link
          href="/benchmarks/new"
          className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-indigo-500"
        >
          Submit Run
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
        <div>
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
            className="mt-1 block rounded-md border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {DOMAIN_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="task-filter"
            className="block text-xs font-medium text-zinc-400"
          >
            Task Type
          </label>
          <input
            id="task-filter"
            type="text"
            value={taskFilter}
            onChange={(e) => setTaskFilter(e.target.value)}
            placeholder="e.g. multiple_choice"
            className="mt-1 block rounded-md border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-xs text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        {(domainFilter || taskFilter) && (
          <div className="self-end">
            <button
              type="button"
              onClick={() => {
                setDomainFilter("");
                setTaskFilter("");
              }}
              className="rounded border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700"
            >
              Reset Filters
            </button>
          </div>
        )}
      </div>

      {loading ? (
        <LoadingState message="Loading leaderboard rankings from public benchmark runs..." />
      ) : error ? (
        <ErrorState
          title="Failed to load leaderboard"
          message={error}
          onRetry={handleRetry}
        />
      ) : groups.length === 0 ? (
        <EmptyState
          title="No completed public runs exist yet"
          message="Leaderboard rankings populate strictly from historical public benchmark runs. No synthetic or placeholder data is displayed."
          actionHref="/benchmarks/new"
          actionLabel="Execute a Benchmark"
        />
      ) : (
        <div className="space-y-8">
          {groups.map((group) => (
            <section
              key={`${group.dataset_id}-${group.protocol_id}-${group.split}-${group.cohort_id ?? ""}`}
              aria-label={`${group.dataset_id} leaderboard`}
              className="space-y-3"
            >
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h2 className="text-lg font-semibold text-white">
                  {group.dataset_id}
                </h2>
                <span className="font-mono text-xs text-zinc-400">
                  {group.protocol_id} · split: {group.split} ·{" "}
                  {group.sample_count ?? "—"} samples
                </span>
              </div>
              <p className="text-xs text-zinc-500">
                Ranks compare only runs sharing this dataset, protocol, split,
                and evaluated sample set.
              </p>
              <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/60">
                <table className="w-full text-left text-sm text-zinc-300">
                  <caption className="sr-only">
                    {group.dataset_id} comparable cohort leaderboard
                  </caption>
                  <thead className="border-b border-zinc-800 bg-zinc-950/80 text-xs uppercase text-zinc-400">
                    <tr>
                      <th scope="col" className="px-4 py-3">Rank</th>
                      <th scope="col" className="px-4 py-3">Model</th>
                      <th scope="col" className="px-4 py-3">Primary Metric</th>
                      <th scope="col" className="px-4 py-3">Latency</th>
                      <th scope="col" className="px-4 py-3">VRAM (est.)</th>
                      <th scope="col" className="px-4 py-3">Samples</th>
                      <th scope="col" className="px-4 py-3">Run ID</th>
                      <th scope="col" className="px-4 py-3">Completed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/80">
                    {group.items.map((item, idx) => (
                      <tr key={`${item.run_id}-${idx}`} className="hover:bg-zinc-800/40">
                        <td className="px-4 py-3 font-semibold text-white whitespace-nowrap">
                          #{idx + 1}
                        </td>
                        <td className="px-4 py-3 font-medium text-white whitespace-nowrap">
                          <div>{item.model_name || item.model_id}</div>
                          <div className="font-mono text-xs text-zinc-500">
                            {item.model_id}
                          </div>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap font-mono font-bold text-emerald-400">
                          <div>
                            {formatMetricValue(
                              item.primary_metric_name,
                              item.primary_metric_value,
                            )}
                          </div>
                          <span className="text-[10px] text-zinc-500 font-sans font-normal">
                            {formatMetricName(item.primary_metric_name)}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-xs text-zinc-300">
                          {formatLatency(item.avg_latency_ms)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-xs text-zinc-300">
                          {/* Model-weight estimate from catalog, not measured peak */}
                          <span title="Estimated model-weight footprint (catalog), not measured peak inference VRAM">
                            {formatVram(item.vram_weight_gb)}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap font-mono text-xs text-zinc-400">
                          {item.sample_count ?? "—"}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-indigo-400 whitespace-nowrap">
                          <Link
                            href={`/benchmarks/${item.run_id}`}
                            className="hover:underline"
                          >
                            {item.run_id.slice(0, 8)}...
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-xs text-zinc-500 whitespace-nowrap">
                          {formatDate(item.completed_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
