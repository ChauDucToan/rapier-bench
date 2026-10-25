"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/formatters";
import { EmptyState, ErrorState, LoadingState } from "@/components/StatusState";
import type { BenchmarkRunResponse } from "@/types/api";

const STATUS_FILTERS = [
  { id: "all", label: "All Runs" },
  { id: "completed", label: "Completed" },
  { id: "running", label: "Running" },
  { id: "queued", label: "Queued" },
  { id: "failed", label: "Failed" },
  { id: "cancelled", label: "Cancelled" },
];

export default function BenchmarksPage() {
  const [runs, setRuns] = useState<BenchmarkRunResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("all");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const PAGE_SIZE = 15;

  useEffect(() => {
    let ignore = false;
    api.benchmarks
      .list({
        status: statusFilter === "all" ? undefined : statusFilter,
        limit: PAGE_SIZE,
        offset,
      })
      .then((res) => {
        if (!ignore) {
          setRuns(res.items);
          setTotal(res.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(
            err instanceof Error ? err.message : "Failed to load benchmark runs",
          );
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [offset, statusFilter]);

  function handleRetry() {
    setLoading(true);
    setError(null);
    api.benchmarks
      .list({
        status: statusFilter === "all" ? undefined : statusFilter,
        limit: PAGE_SIZE,
        offset,
      })
      .then((res) => {
        setRuns(res.items);
        setTotal(res.total);
        setLoading(false);
      })
      .catch((err) => {
        setError(
          err instanceof Error ? err.message : "Failed to load benchmark runs",
        );
        setLoading(false);
      });
  }

  function handleFilterChange(newFilter: string) {
    setStatusFilter(newFilter);
    setOffset(0);
  }

  return (
    <div className="py-6 space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Benchmark Executions
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Active and historical evaluation runs across registered model checkpoints.
          </p>
        </div>
        <Link
          href="/benchmarks/new"
          className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-indigo-500"
        >
          New Benchmark Run
        </Link>
      </div>

      {/* Filter tabs */}
      <div className="flex flex-wrap gap-2 border-b border-zinc-800 pb-3" role="tablist" aria-label="Run Status Filters">
        {STATUS_FILTERS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={statusFilter === tab.id}
            onClick={() => handleFilterChange(tab.id)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
              statusFilter === tab.id
                ? "bg-zinc-800 text-white font-semibold"
                : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <LoadingState message="Loading benchmark runs..." />
      ) : error ? (
        <ErrorState
          title="Failed to load runs"
          message={error}
          onRetry={handleRetry}
        />
      ) : runs.length === 0 ? (
        <EmptyState
          title="No benchmark runs found"
          message={
            statusFilter === "all"
              ? "No benchmark runs have been executed yet."
              : `No runs currently match the "${statusFilter}" filter.`
          }
          actionHref="/benchmarks/new"
          actionLabel="Queue First Run"
        />
      ) : (
        <div className="space-y-4">
          <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/60">
            <table className="w-full text-left text-sm text-zinc-300">
              <caption className="sr-only">Benchmark Runs Table</caption>
              <thead className="border-b border-zinc-800 bg-zinc-950/80 text-xs uppercase text-zinc-400">
                <tr>
                  <th scope="col" className="px-4 py-3">Run ID</th>
                  <th scope="col" className="px-4 py-3">Model</th>
                  <th scope="col" className="px-4 py-3">Dataset</th>
                  <th scope="col" className="px-4 py-3">Protocol</th>
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
                    <td className="px-4 py-3 font-mono text-xs text-zinc-400 max-w-xs truncate" title={r.protocol_id}>
                      {r.protocol_id}
                    </td>
                    <td className="px-4 py-3 text-xs text-zinc-400 capitalize whitespace-nowrap">
                      {r.sample_size_mode} ({r.sample_count})
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

          {/* Pagination */}
          <div className="flex items-center justify-between text-xs text-zinc-400 pt-2">
            <div>
              Showing {offset + 1}–{Math.min(offset + runs.length, total)} of{" "}
              {total} runs
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                className="rounded border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>
              <button
                type="button"
                disabled={offset + runs.length >= total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
                className="rounded border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
