"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import {
  formatDate,
  formatLatency,
  formatMetricName,
  formatMetricValue,
} from "@/lib/formatters";
import { EmptyState, ErrorState, LoadingState } from "@/components/StatusState";
import type {
  BenchmarkRunResponse,
  PredictionRecord,
  RunResultsResponse,
  RunStatus,
} from "@/types/api";

interface BenchmarkDetailClientProps {
  runId: string;
}

export function BenchmarkDetailClient({ runId }: BenchmarkDetailClientProps) {
  const router = useRouter();

  const [run, setRun] = useState<BenchmarkRunResponse | null>(null);
  const [results, setResults] = useState<RunResultsResponse | null>(null);
  const [predictions, setPredictions] = useState<PredictionRecord[]>([]);
  const [predictionsTotal, setPredictionsTotal] = useState<number>(0);
  const [predictionsOffset, setPredictionsOffset] = useState<number>(0);
  const [predictionFilter, setPredictionFilter] = useState<string>("all");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isTerminalRef = useRef<boolean>(false);

  const PREDICTIONS_PAGE_SIZE = 20;

  const loadPredictions = useCallback(
    async (offset: number, filter: string) => {
      try {
        const queryFilter = filter === "all" ? undefined : filter;
        const res = await api.benchmarks.getPredictions(runId, {
          limit: PREDICTIONS_PAGE_SIZE,
          offset,
          status: queryFilter,
        });
        setPredictions(res.items);
        setPredictionsTotal(res.total);
      } catch {
        // Predictions might not exist yet if run is not completed
        setPredictions([]);
      }
    },
    [runId],
  );

  const loadResults = useCallback(async () => {
    try {
      const res = await api.benchmarks.getResults(runId);
      setResults(res);
    } catch {
      // Results not ready yet
    }
  }, [runId]);

  const fetchFullRun = useCallback(async () => {
    try {
      const runData = await api.benchmarks.get(runId);
      setRun(runData);

      const status = runData.status;
      if (
        status === "completed" ||
        status === "failed" ||
        status === "cancelled"
      ) {
        isTerminalRef.current = true;
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
        if (status === "completed") {
          void loadResults();
          void loadPredictions(0, predictionFilter);
        }
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("Benchmark run not found or you do not have permission to view it.");
      } else {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load benchmark telemetry",
        );
      }
      isTerminalRef.current = true;
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    } finally {
      setLoading(false);
    }
  }, [runId, loadResults, loadPredictions, predictionFilter]);

  const pollStatus = useCallback(async () => {
    if (isTerminalRef.current) return;
    try {
      const statusRes = await api.benchmarks.getStatus(runId);
      setRun((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          status: statusRes.status,
          progress_done: statusRes.progress_done,
          progress_total: statusRes.progress_total,
          cancel_requested: statusRes.cancel_requested,
          error_text: statusRes.error_text,
        };
      });

      if (
        statusRes.status === "completed" ||
        statusRes.status === "failed" ||
        statusRes.status === "cancelled"
      ) {
        isTerminalRef.current = true;
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
        void fetchFullRun();
      }
    } catch {
      // transient network poll error
    }
  }, [runId, fetchFullRun]);

  useEffect(() => {
    isTerminalRef.current = false;
    let ignore = false;

    api.benchmarks
      .get(runId)
      .then((runData) => {
        if (ignore) return;
        setRun(runData);
        setLoading(false);

        const status = runData.status;
        if (
          status === "completed" ||
          status === "failed" ||
          status === "cancelled"
        ) {
          isTerminalRef.current = true;
          if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }
          if (status === "completed") {
            void loadResults();
            void loadPredictions(0, predictionFilter);
          }
        }
      })
      .catch((err) => {
        if (ignore) return;
        setLoading(false);
        isTerminalRef.current = true;
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
        if (err instanceof ApiError && err.status === 404) {
          setError(
            "Benchmark run not found or you do not have permission to view it.",
          );
        } else {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load benchmark telemetry",
          );
        }
      });

    pollTimerRef.current = setInterval(() => {
      void pollStatus();
    }, 2500);

    return () => {
      ignore = true;
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [runId, loadResults, loadPredictions, pollStatus, predictionFilter]);

  async function handleCancel() {
    setActionLoading(true);
    setActionError(null);
    try {
      await api.benchmarks.cancel(runId);
      void pollStatus();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Failed to cancel benchmark",
      );
    } finally {
      setActionLoading(false);
    }
  }

  async function handleRerun() {
    setActionLoading(true);
    setActionError(null);
    try {
      const newRun = await api.benchmarks.rerun(runId);
      router.push(`/benchmarks/${newRun.id}`);
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Failed to rerun benchmark",
      );
    } finally {
      setActionLoading(false);
    }
  }

  function handleFilterChange(filter: string) {
    setPredictionFilter(filter);
    setPredictionsOffset(0);
    void loadPredictions(0, filter);
  }

  function handlePageChange(newOffset: number) {
    setPredictionsOffset(newOffset);
    void loadPredictions(newOffset, predictionFilter);
  }

  if (loading) {
    return <LoadingState message="Loading benchmark run and execution state..." />;
  }

  if (error || !run) {
    return (
      <div className="py-6">
        <ErrorState
          title="Benchmark Run Unavailable"
          message={error || "Run not found"}
        />
        <div className="mt-4 text-center">
          <Link
            href="/benchmarks"
            className="text-xs text-indigo-400 hover:text-indigo-300 underline"
          >
            ← Back to Runs List
          </Link>
        </div>
      </div>
    );
  }

  const isRunningOrQueued =
    run.status === ("queued" as RunStatus) ||
    run.status === ("running" as RunStatus);

  const progressTotal = run.progress_total || 0;
  const progressDone = run.progress_done || 0;
  const progressPct =
    progressTotal > 0
      ? Math.min(100, Math.round((progressDone / progressTotal) * 100))
      : 0;

  const shortfall = run.sample_selection?.shortfall ?? 0;

  return (
    <div className="py-6 space-y-8">
      {/* Header section */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white font-mono">
              Run {run.id.slice(0, 8)}...
            </h1>
            <span
              className={`inline-flex items-center rounded px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider ${
                run.status === "completed"
                  ? "bg-emerald-950/80 text-emerald-300 border border-emerald-800/60"
                  : run.status === "running"
                  ? "bg-blue-950/80 text-blue-300 border border-blue-800/60"
                  : run.status === "failed"
                  ? "bg-red-950/80 text-red-300 border border-red-800/60"
                  : run.status === "cancelled"
                  ? "bg-zinc-800 text-zinc-400"
                  : "bg-amber-950/80 text-amber-300 border border-amber-800/60"
              }`}
            >
              {run.status}
            </span>
            {run.is_private && (
              <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">
                Private
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-zinc-400 font-mono">
            {run.id}
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {isRunningOrQueued && (
            <button
              type="button"
              onClick={() => void handleCancel()}
              disabled={actionLoading || run.cancel_requested}
              className="rounded-md border border-red-700 bg-red-950/60 px-3.5 py-1.5 text-xs font-medium text-red-200 transition hover:bg-red-900/60 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-red-500"
            >
              {run.cancel_requested ? "Cancelling..." : "Cancel Run"}
            </button>
          )}

          {!isRunningOrQueued && (
            <button
              type="button"
              onClick={() => void handleRerun()}
              disabled={actionLoading}
              className="rounded-md border border-zinc-700 bg-zinc-800 px-3.5 py-1.5 text-xs font-medium text-zinc-200 transition hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-indigo-500"
            >
              Rerun Benchmark
            </button>
          )}

          {run.status === "completed" && (
            <div className="flex items-center gap-1.5">
              <a
                href={api.benchmarks.getExportUrl(run.id, "jsonl")}
                download={`run_${run.id}.jsonl`}
                className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:bg-zinc-800 hover:text-white focus-visible:outline-2 focus-visible:outline-indigo-500"
              >
                Export JSONL
              </a>
              <a
                href={api.benchmarks.getExportUrl(run.id, "csv")}
                download={`run_${run.id}.csv`}
                className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:bg-zinc-800 hover:text-white focus-visible:outline-2 focus-visible:outline-indigo-500"
              >
                Export CSV
              </a>
            </div>
          )}
        </div>
      </div>

      {actionError && (
        <div
          role="alert"
          aria-live="polite"
          className="rounded-md border border-red-800/60 bg-red-950/40 p-3 text-xs text-red-300"
        >
          {actionError}
        </div>
      )}

      {/* Progress bar */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-3">
        <div className="flex items-center justify-between text-xs text-zinc-400">
          <span className="font-semibold text-white">Execution Progress</span>
          <span className="font-mono">
            {progressDone} / {progressTotal} samples ({progressPct}%)
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={progressPct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-live="polite"
          className="h-2.5 w-full overflow-hidden rounded-full bg-zinc-800"
        >
          <div
            className={`h-full transition-all duration-500 ${
              run.status === "completed"
                ? "bg-emerald-500"
                : run.status === "failed"
                ? "bg-red-500"
                : "bg-indigo-500"
            }`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
        {run.error_text && (
          <div
            role="alert"
            className="rounded border border-red-800/60 bg-red-950/30 p-2.5 text-xs text-red-300"
          >
            <span className="font-semibold">Error:</span> {run.error_text}
          </div>
        )}
      </div>

      {/* Shortfall report warning */}
      {Number(shortfall) > 0 && (
        <div
          role="status"
          aria-live="polite"
          className="rounded-xl border border-amber-800/60 bg-amber-950/30 p-4 text-xs text-amber-200"
        >
          <div className="font-semibold text-amber-100">
            Deterministic Shortfall Surfaced (§11.2)
          </div>
          <p className="mt-1">
            Requested {run.sample_selection?.requested_samples} samples, but only{" "}
            {run.sample_selection?.actual_samples} met the strict suite eligibility filter.
            Evaluated on all {run.sample_selection?.actual_samples} eligible records (shortfall:{" "}
            {shortfall}).
          </p>
        </div>
      )}

      {/* Configuration & Hardware Metadata */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-3">
          <h2 className="text-sm font-semibold text-white">Configuration Parameters</h2>
          <dl className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <dt className="text-zinc-500">Model ID</dt>
              <dd className="font-mono text-zinc-200">{run.model_id}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Dataset ID</dt>
              <dd className="font-mono text-zinc-200">{run.dataset_id}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Protocol ID</dt>
              <dd className="font-mono text-zinc-200">{run.protocol_id}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Split</dt>
              <dd className="font-mono text-zinc-200">{run.split}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Sample Mode</dt>
              <dd className="capitalize text-zinc-200">
                {run.sample_size_mode} ({run.sample_count} requested)
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Deterministic Seed</dt>
              <dd className="font-mono text-zinc-200">{run.seed}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Created At</dt>
              <dd className="text-zinc-200">{formatDate(run.created_at)}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Completed At</dt>
              <dd className="text-zinc-200">
                {run.completed_at ? formatDate(run.completed_at) : "In progress"}
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-3">
          <h2 className="text-sm font-semibold text-white">Hardware & Telemetry</h2>
          {run.hardware_metadata || results?.hardware_metadata ? (
            <dl className="grid grid-cols-2 gap-3 text-xs">
              {Object.entries(
                (run.hardware_metadata || results?.hardware_metadata) ?? {},
              ).map(([k, v]) => (
                <div key={k}>
                  <dt className="text-zinc-500 uppercase">{k.replace(/_/g, " ")}</dt>
                  <dd className="font-mono text-zinc-200">
                    {typeof v === "object" ? JSON.stringify(v) : String(v)}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-xs text-zinc-500">
              Hardware telemetry will populate upon runner allocation.
            </p>
          )}
        </div>
      </div>

      {/* Results Metrics Panel (Task 7) */}
      {run.status === "completed" && results && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white">
            Evaluation Metrics
          </h2>

          {Object.keys(results.metrics || {}).length === 0 ? (
            <p className="text-xs text-zinc-500">No metrics returned for this run.</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {Object.entries(results.metrics).map(([metricKey, metricVal]) => (
                <div
                  key={metricKey}
                  className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4"
                >
                  <dt className="text-xs font-medium text-zinc-400">
                    {formatMetricName(metricKey)}
                  </dt>
                  <dd className="mt-1 text-2xl font-bold tracking-tight text-white font-mono">
                    {formatMetricValue(metricKey, metricVal)}
                  </dd>
                  <span className="text-[10px] font-mono text-zinc-500">
                    {metricKey}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Predictions Browser & Failure Analysis (Task 7) */}
      {run.status === "completed" && (
        <div className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-semibold text-white">
              Prediction Records & Failure Analysis
            </h2>

            {/* Filter buttons */}
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Prediction Filters">
              {[
                { id: "all", label: "All Records" },
                { id: "correct", label: "Correct" },
                { id: "incorrect", label: "Incorrect" },
                { id: "parse_failure", label: "Parse Failure" },
              ].map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => handleFilterChange(f.id)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                    predictionFilter === f.id
                      ? "bg-indigo-600 text-white"
                      : "border border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {predictions.length === 0 ? (
            <EmptyState
              title="No predictions match filter"
              message={`No records found matching status "${predictionFilter}".`}
            />
          ) : (
            <>
              <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/60">
                <table className="w-full text-left text-xs text-zinc-300">
                  <caption className="sr-only">Benchmark Prediction Records</caption>
                  <thead className="border-b border-zinc-800 bg-zinc-950/80 text-[11px] uppercase text-zinc-400">
                    <tr>
                      <th scope="col" className="px-3 py-2.5">Sample ID</th>
                      <th scope="col" className="px-3 py-2.5">Target / Gold</th>
                      <th scope="col" className="px-3 py-2.5">Raw Model Output</th>
                      <th scope="col" className="px-3 py-2.5">Parsed</th>
                      <th scope="col" className="px-3 py-2.5">Status</th>
                      <th scope="col" className="px-3 py-2.5">Latency</th>
                      <th scope="col" className="px-3 py-2.5">Tokens</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/80 font-mono">
                    {predictions.map((p, idx) => {
                      const isCorrect = p.is_correct;
                      return (
                        <tr key={`${p.sample_id}-${idx}`} className="hover:bg-zinc-800/40">
                          <td className="px-3 py-2 text-zinc-400 whitespace-nowrap">
                            {p.sample_id}
                          </td>
                          <td className="px-3 py-2 text-zinc-200 max-w-xs truncate" title={typeof p.target === "object" ? JSON.stringify(p.target) : String(p.target ?? "—")}>
                            {typeof p.target === "object"
                              ? JSON.stringify(p.target)
                              : String(p.target ?? "—")}
                          </td>
                          <td className="px-3 py-2 text-zinc-300 max-w-sm truncate" title={p.raw_output}>
                            {p.raw_output || "—"}
                          </td>
                          <td className="px-3 py-2 text-white max-w-xs truncate" title={typeof p.parsed_output === "object" ? JSON.stringify(p.parsed_output) : String(p.parsed_output ?? "—")}>
                            {typeof p.parsed_output === "object"
                              ? JSON.stringify(p.parsed_output)
                              : String(p.parsed_output ?? "—")}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap">
                            <div className="flex items-center gap-1.5">
                              <span
                                className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                                  p.parse_status === "success"
                                    ? "bg-zinc-800 text-zinc-300"
                                    : "bg-amber-950 text-amber-300 border border-amber-800/40"
                                }`}
                              >
                                {p.parse_status || "unknown"}
                              </span>
                              {isCorrect !== undefined && isCorrect !== null && (
                                <span
                                  className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                                    isCorrect
                                      ? "bg-emerald-950 text-emerald-300 border border-emerald-800/60"
                                      : "bg-red-950 text-red-300 border border-red-800/60"
                                  }`}
                                >
                                  {isCorrect ? "PASS" : "FAIL"}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-zinc-400">
                            {formatLatency(p.latency_ms)}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-zinc-400">
                            {p.input_tokens ?? "—"} / {p.output_tokens ?? "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination controls */}
              <div className="flex items-center justify-between text-xs text-zinc-400">
                <div>
                  Showing {predictionsOffset + 1}–
                  {Math.min(predictionsOffset + predictions.length, predictionsTotal)} of{" "}
                  {predictionsTotal} records
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={predictionsOffset === 0}
                    onClick={() =>
                      handlePageChange(
                        Math.max(0, predictionsOffset - PREDICTIONS_PAGE_SIZE),
                      )
                    }
                    className="rounded border border-zinc-700 bg-zinc-800 px-2.5 py-1 text-xs text-zinc-300 hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    disabled={
                      predictionsOffset + predictions.length >= predictionsTotal
                    }
                    onClick={() =>
                      handlePageChange(predictionsOffset + PREDICTIONS_PAGE_SIZE)
                    }
                    className="rounded border border-zinc-700 bg-zinc-800 px-2.5 py-1 text-xs text-zinc-300 hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
