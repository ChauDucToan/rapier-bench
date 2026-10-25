"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import {
  formatDate,
  formatMetricName,
  formatMetricValue,
} from "@/lib/formatters";
import { EmptyState, ErrorState, LoadingState } from "@/components/StatusState";
import type { BenchmarkRunResponse, ComparisonResponse } from "@/types/api";

const DATASET_PRIMARY_METRICS: Record<string, string> = {
  sciq: "accuracy",
  wdc_pave: "micro_f1",
  legalbench_contract_nli: "balanced_accuracy",
  ifeval: "prompt_level_strict_acc",
  faitheval: "balanced_score",
};

export default function ComparePage() {
  const [completedRuns, setCompletedRuns] = useState<BenchmarkRunResponse[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);

  const [loadingRuns, setLoadingRuns] = useState(true);
  const [loadingComparison, setLoadingComparison] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    api.benchmarks
      .list({
        status: "completed",
        limit: 50,
      })
      .then((res) => {
        if (!ignore) {
          setCompletedRuns(res.items);
          setLoadingRuns(false);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load completed benchmark runs",
          );
          setLoadingRuns(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, []);

  const firstSelectedRun = completedRuns.find((r) => r.id === selectedIds[0]);

  function isCompatible(candidate: BenchmarkRunResponse): boolean {
    if (!firstSelectedRun) return true;
    return (
      candidate.dataset_id === firstSelectedRun.dataset_id &&
      candidate.protocol_id === firstSelectedRun.protocol_id &&
      candidate.split === firstSelectedRun.split
    );
  }

  function toggleRunSelection(runId: string) {
    if (selectedIds.includes(runId)) {
      const next = selectedIds.filter((id) => id !== runId);
      setSelectedIds(next);
      if (next.length < 2) {
        setComparison(null);
      }
    } else {
      if (selectedIds.length >= 4) {
        return;
      }
      const next = [...selectedIds, runId];
      setSelectedIds(next);
      if (next.length >= 2) {
        setLoadingComparison(true);
      }
    }
  }

  useEffect(() => {
    let ignore = false;
    if (selectedIds.length < 2) {
      return;
    }

    api.comparisons
      .get(selectedIds)
      .then((res) => {
        if (!ignore) {
          setComparison(res);
          setLoadingComparison(false);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(
            err instanceof Error ? err.message : "Failed to compute comparison",
          );
          setLoadingComparison(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [selectedIds]);

  // Primary metric for chart
  const primaryMetricKey = firstSelectedRun
    ? DATASET_PRIMARY_METRICS[firstSelectedRun.dataset_id] || "accuracy"
    : "accuracy";

  // Recharts data
  const chartData = (comparison?.runs || []).map((r) => {
    let val = 0;
    if (comparison?.metrics_comparison) {
      // metric -> run_id -> val or run_id -> metric -> val
      const fromMetricKey = comparison.metrics_comparison[primaryMetricKey]?.[r.id];
      const fromRunKey = comparison.metrics_comparison[r.id]?.[primaryMetricKey];
      val = fromMetricKey ?? fromRunKey ?? 0;
    }
    return {
      runId: r.id.slice(0, 8),
      model: r.model_id,
      [formatMetricName(primaryMetricKey)]:
        val <= 1.0 && val >= 0.0 ? Math.round(val * 1000) / 10 : val,
    };
  });

  return (
    <div className="py-6 space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Run Comparison
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Side-by-side empirical comparison across 2 to 4 runs sharing identical evaluation contracts.
        </p>
      </div>

      {/* Mandatory Comparability Rule Notice */}
      <div
        role="region"
        aria-label="Comparability Contract"
        className="rounded-xl border border-indigo-800/60 bg-indigo-950/30 p-4 text-xs text-indigo-200"
      >
        <div className="font-semibold text-indigo-100 uppercase tracking-wider">
          Comparability Rule
        </div>
        <p className="mt-1 text-indigo-300">
          Runs are strictly comparable only when evaluated on the identical dataset, evaluation protocol, and dataset split. Incompatible candidates are disabled automatically.
        </p>
      </div>

      {error && (
        <ErrorState
          title="Comparison error"
          message={error}
          onRetry={() => setSelectedIds([...selectedIds])}
        />
      )}

      {loadingRuns ? (
        <LoadingState message="Loading completed benchmark runs for comparison..." />
      ) : completedRuns.length === 0 ? (
        <EmptyState
          title="No completed runs available"
          message="Run comparison requires at least 2 completed benchmarks on the same dataset."
          actionHref="/benchmarks/new"
          actionLabel="Launch First Benchmark"
        />
      ) : (
        <div className="space-y-6">
          {/* Run Selection Panel */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">
                Select 2–4 Comparable Runs ({selectedIds.length} selected)
              </h2>
              {selectedIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedIds([])}
                  className="text-xs text-zinc-400 hover:text-white"
                >
                  Clear Selection
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
              {completedRuns.map((r) => {
                const isSelected = selectedIds.includes(r.id);
                const compatible = isCompatible(r);
                const disabled = !isSelected && (!compatible || selectedIds.length >= 4);

                return (
                  <label
                    key={r.id}
                    className={`flex items-start gap-3 rounded-lg border p-3 text-xs transition cursor-pointer ${
                      isSelected
                        ? "border-indigo-600 bg-indigo-950/40 text-white"
                        : disabled
                        ? "border-zinc-800/40 bg-zinc-950/40 text-zinc-600 cursor-not-allowed opacity-60"
                        : "border-zinc-800 bg-zinc-950 text-zinc-300 hover:border-zinc-700 hover:bg-zinc-900/80"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      disabled={disabled}
                      onChange={() => toggleRunSelection(r.id)}
                      className="mt-0.5 h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-indigo-600 focus:ring-indigo-500"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-white truncate">
                        {r.model_id}
                      </div>
                      <div className="font-mono text-[11px] text-zinc-400">
                        {r.dataset_id} • {r.protocol_id}
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-[10px] text-zinc-500">
                        <span>Split: {r.split}</span>
                        <span>•</span>
                        <span>{formatDate(r.created_at)}</span>
                      </div>
                      {!compatible && firstSelectedRun && (
                        <div className="mt-1 text-[10px] text-amber-500 font-medium">
                          Incompatible dataset/protocol
                        </div>
                      )}
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Comparison Output */}
          {selectedIds.length < 2 ? (
            <div className="rounded-xl border border-dashed border-zinc-800 p-8 text-center text-xs text-zinc-500">
              Select at least 2 comparable runs from the list above to render the side-by-side comparison.
            </div>
          ) : loadingComparison ? (
            <LoadingState message="Computing differential metric comparisons..." />
          ) : comparison ? (
            <div className="space-y-8">
              {/* Primary Metric Chart */}
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 space-y-4">
                <h3 className="text-base font-semibold text-white">
                  Primary Metric Comparison: {formatMetricName(primaryMetricKey)}
                </h3>
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={chartData}
                      margin={{ top: 20, right: 30, left: 10, bottom: 20 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                      <XAxis
                        dataKey="model"
                        stroke="#a1a1aa"
                        fontSize={12}
                        tickLine={false}
                      />
                      <YAxis
                        stroke="#a1a1aa"
                        fontSize={12}
                        tickLine={false}
                        domain={[0, "auto"]}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#18181b",
                          borderColor: "#3f3f46",
                          color: "#f4f4f5",
                          borderRadius: "0.5rem",
                          fontSize: "12px",
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: "12px", color: "#a1a1aa" }} />
                      <Bar
                        dataKey={formatMetricName(primaryMetricKey)}
                        fill="#6366f1"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Differential Metrics Table */}
              <div className="space-y-3">
                <h3 className="text-base font-semibold text-white">
                  Metrics Breakdown
                </h3>
                <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/60">
                  <table className="w-full text-left text-xs text-zinc-300">
                    <caption className="sr-only">Side-by-side run metrics</caption>
                    <thead className="border-b border-zinc-800 bg-zinc-950/80 uppercase text-zinc-400">
                      <tr>
                        <th scope="col" className="px-4 py-3">Metric</th>
                        {comparison.runs.map((r) => (
                          <th key={r.id} scope="col" className="px-4 py-3 font-mono">
                            <div>{r.model_id}</div>
                            <div className="text-[10px] text-zinc-500 lowercase">
                              <Link
                                href={`/benchmarks/${r.id}`}
                                className="hover:underline text-indigo-400"
                              >
                                {r.id.slice(0, 8)}
                              </Link>
                            </div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/80 font-mono">
                      {Object.keys(comparison.metrics_comparison).map((metricKey) => (
                        <tr key={metricKey} className="hover:bg-zinc-800/40">
                          <td className="px-4 py-3 font-sans font-medium text-white whitespace-nowrap">
                            {formatMetricName(metricKey)}
                            <span className="block text-[10px] text-zinc-500 font-mono">
                              {metricKey}
                            </span>
                          </td>
                          {comparison.runs.map((r) => {
                            const val =
                              comparison.metrics_comparison[metricKey]?.[r.id] ??
                              comparison.metrics_comparison[r.id]?.[metricKey];
                            return (
                              <td
                                key={`${metricKey}-${r.id}`}
                                className="px-4 py-3 whitespace-nowrap font-semibold text-zinc-200"
                              >
                                {formatMetricValue(metricKey, val)}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
