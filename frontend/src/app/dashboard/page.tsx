"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/formatters";
import { EmptyState, ErrorState, LoadingState } from "@/components/StatusState";
import type { BenchmarkRunResponse } from "@/types/api";

export default function DashboardPage() {
  const [modelCount, setModelCount] = useState<number | null>(null);
  const [datasetCount, setDatasetCount] = useState<number | null>(null);
  const [runs, setRuns] = useState<BenchmarkRunResponse[]>([]);
  const [totalRuns, setTotalRuns] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    Promise.all([
      api.models.list().catch(() => []),
      api.datasets.list().catch(() => []),
      api.benchmarks
        .list({ limit: 5 })
        .catch(() => ({ items: [], total: 0, limit: 5, offset: 0 })),
    ])
      .then(([modelsData, datasetsData, runsData]) => {
        if (!ignore) {
          setModelCount(modelsData.length);
          setDatasetCount(datasetsData.length);
          setRuns(runsData.items);
          setTotalRuns(runsData.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(
            err instanceof Error ? err.message : "Failed to load dashboard metrics",
          );
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, []);
  function handleRefresh() {
    setLoading(true);
    setError(null);
    Promise.all([
      api.models.list().catch(() => []),
      api.datasets.list().catch(() => []),
      api.benchmarks
        .list({ limit: 5 })
        .catch(() => ({ items: [], total: 0, limit: 5, offset: 0 })),
    ])
      .then(([modelsData, datasetsData, runsData]) => {
        setModelCount(modelsData.length);
        setDatasetCount(datasetsData.length);
        setRuns(runsData.items);
        setTotalRuns(runsData.total);
        setLoading(false);
      })
      .catch((err) => {
        setError(
          err instanceof Error ? err.message : "Failed to load dashboard metrics",
        );
        setLoading(false);
      });
  }

  return (
    <div className="py-6 space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Benchmark Dashboard
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            System overview, registered catalog dimensions, and recent evaluation workloads.
          </p>
        </div>
        <Link
          href="/benchmarks/new"
          className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
        >
          New Benchmark Run
        </Link>
      </div>

      {loading ? (
        <LoadingState message="Loading platform overview..." />
      ) : error ? (
        <ErrorState
          title="Dashboard unavailable"
          message={error}
          onRetry={handleRefresh}
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">
                Registered Models
              </span>
              <p className="mt-2 text-3xl font-bold tracking-tight text-white">
                {modelCount ?? "—"}
              </p>
              <Link
                href="/models"
                className="mt-3 inline-block text-xs font-medium text-indigo-400 hover:text-indigo-300"
              >
                View models catalog →
              </Link>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">
                Registered Datasets
              </span>
              <p className="mt-2 text-3xl font-bold tracking-tight text-white">
                {datasetCount ?? "—"}
              </p>
              <Link
                href="/datasets"
                className="mt-3 inline-block text-xs font-medium text-indigo-400 hover:text-indigo-300"
              >
                View dataset suites →
              </Link>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">
                Total Benchmark Runs
              </span>
              <p className="mt-2 text-3xl font-bold tracking-tight text-white">
                {totalRuns ?? 0}
              </p>
              <Link
                href="/benchmarks"
                className="mt-3 inline-block text-xs font-medium text-indigo-400 hover:text-indigo-300"
              >
                Browse all runs →
              </Link>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">
                Quick Actions
              </span>
              <div className="mt-3 flex flex-col gap-2">
                <Link
                  href="/recommend"
                  className="text-xs font-medium text-indigo-400 hover:text-indigo-300"
                >
                  Model Recommendations →
                </Link>
                <Link
                  href="/leaderboard"
                  className="text-xs font-medium text-indigo-400 hover:text-indigo-300"
                >
                  Public Leaderboard →
                </Link>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">
                Recent Benchmark Runs
              </h2>
              {runs.length > 0 && (
                <Link
                  href="/benchmarks"
                  className="text-xs font-medium text-indigo-400 hover:text-indigo-300"
                >
                  View all runs ({totalRuns ?? runs.length})
                </Link>
              )}
            </div>

            {runs.length === 0 ? (
              <EmptyState
                title="No benchmark runs executed"
                message="Launch your first empirical benchmark run to inspect model accuracy, throughput, and token outputs."
                actionHref="/benchmarks/new"
                actionLabel="Configure Benchmark"
              />
            ) : (
              <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/60">
                <table className="w-full text-left text-sm text-zinc-300">
                  <caption className="sr-only">Recent Benchmark Runs</caption>
                  <thead className="border-b border-zinc-800 bg-zinc-950/80 text-xs uppercase text-zinc-400">
                    <tr>
                      <th scope="col" className="px-4 py-3">Run ID</th>
                      <th scope="col" className="px-4 py-3">Model</th>
                      <th scope="col" className="px-4 py-3">Dataset</th>
                      <th scope="col" className="px-4 py-3">Mode</th>
                      <th scope="col" className="px-4 py-3">Status</th>
                      <th scope="col" className="px-4 py-3">Progress</th>
                      <th scope="col" className="px-4 py-3">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/80">
                    {runs.map((r) => (
                      <tr key={r.id} className="hover:bg-zinc-800/40">
                        <td className="px-4 py-3 font-mono text-xs text-indigo-400 whitespace-nowrap">
                          <Link
                            href={`/benchmarks/${r.id}`}
                            className="hover:underline focus-visible:outline-2 focus-visible:outline-indigo-500 rounded"
                          >
                            {r.id.slice(0, 8)}...
                          </Link>
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-white whitespace-nowrap">
                          {r.model_id}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-zinc-300 whitespace-nowrap">
                          {r.dataset_id}
                        </td>
                        <td className="px-4 py-3 text-xs text-zinc-400 capitalize whitespace-nowrap">
                          {r.sample_size_mode}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium uppercase tracking-wider ${
                              r.status === "completed"
                                ? "bg-emerald-950/80 text-emerald-300 border border-emerald-800/60"
                                : r.status === "running"
                                ? "bg-blue-950/80 text-blue-300 border border-blue-800/60"
                                : r.status === "failed"
                                ? "bg-red-950/80 text-red-300 border border-red-800/60"
                                : r.status === "cancelled"
                                ? "bg-zinc-800 text-zinc-400"
                                : "bg-amber-950/80 text-amber-300 border border-amber-800/60"
                            }`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-xs font-mono text-zinc-400">
                          {r.progress_done} / {r.progress_total}
                        </td>
                        <td className="px-4 py-3 text-xs text-zinc-500 whitespace-nowrap">
                          {formatDate(r.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
