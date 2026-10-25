"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { LoadingState } from "@/components/StatusState";
import type { DatasetResponse, ModelResponse } from "@/types/api";

const PROTOCOLS_BY_DATASET: Record<
  string,
  Array<{ id: string; name: string; description: string }>
> = {
  sciq: [
    {
      id: "sciq_evidence_grounded",
      name: "Evidence Grounded (Recommended)",
      description: "Presents supporting passage context alongside the multiple choice question.",
    },
    {
      id: "sciq_closed_book",
      name: "Closed Book Protocol",
      description: "Evaluates internal parametric memory without supporting context passage.",
    },
  ],
  wdc_pave: [
    {
      id: "wdc_pave_extraction",
      name: "Product Attribute Extraction",
      description: "Extracts brand and product attributes into structured JSON.",
    },
  ],
  legalbench_contract_nli: [
    {
      id: "legalbench_contract_nli_binary",
      name: "Contract NLI Binary Classification",
      description: "Evaluates clause-hypothesis entailment with balanced accuracy.",
    },
  ],
  ifeval: [
    {
      id: "ifeval_default",
      name: "Instruction Following Evaluation",
      description: "Strict and loose verifiable constraint satisfaction.",
    },
  ],
  faitheval: [
    {
      id: "faitheval_unanswerable_v1",
      name: "Contextual Faithfulness Protocol",
      description: "Measures unanswerable abstention vs answerable control accuracy.",
    },
  ],
};

const DEFAULT_SAMPLE_COUNTS: Record<string, number> = {
  smoke: 10,
  pilot: 25,
  standard: 100,
};

export default function NewBenchmarkPage() {
  const router = useRouter();

  const [models, setModels] = useState<ModelResponse[]>([]);
  const [datasets, setDatasets] = useState<DatasetResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  const [selectedDomain, setSelectedDomain] = useState<string>("");
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [selectedProtocolId, setSelectedProtocolId] = useState<string>("");
  const [selectedModelId, setSelectedModelId] = useState<string>("");
  const [sampleMode, setSampleMode] = useState<string>("smoke");
  const [customSampleCount, setCustomSampleCount] = useState<number>(50);
  const [seed, setSeed] = useState<number>(42);
  const [isPrivate, setIsPrivate] = useState<boolean>(true);

  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [shortfallNotice, setShortfallNotice] = useState<string | null>(null);

  useEffect(() => {
    async function loadCatalogs() {
      setLoading(true);
      try {
        const [modelsList, datasetsList] = await Promise.all([
          api.models.list(),
          api.datasets.list(),
        ]);
        setModels(modelsList);
        setDatasets(datasetsList);

        if (datasetsList.length > 0) {
          const first = datasetsList[0];
          setSelectedDomain(first.domain);
          setSelectedDatasetId(first.id);
          const proto =
            first.default_protocol_id ||
            PROTOCOLS_BY_DATASET[first.id]?.[0]?.id ||
            "";
          setSelectedProtocolId(proto);
        }
        if (modelsList.length > 0) {
          setSelectedModelId(modelsList[0].id);
        }
      } catch (err) {
        setPageError(
          err instanceof Error
            ? err.message
            : "Failed to load benchmark configurations",
        );
      } finally {
        setLoading(false);
      }
    }
    void loadCatalogs();
  }, []);

  const domains = Array.from(new Set(datasets.map((d) => d.domain)));
  const filteredDatasets = datasets.filter((d) =>
    selectedDomain ? d.domain === selectedDomain : true,
  );

  const activeDataset = datasets.find((d) => d.id === selectedDatasetId);
  const availableProtocols = selectedDatasetId
    ? PROTOCOLS_BY_DATASET[selectedDatasetId] || []
    : [];

  function handleDomainChange(newDomain: string) {
    setSelectedDomain(newDomain);
    const matching = datasets.filter((d) => d.domain === newDomain);
    if (matching.length > 0) {
      const first = matching[0];
      setSelectedDatasetId(first.id);
      const proto =
        first.default_protocol_id ||
        PROTOCOLS_BY_DATASET[first.id]?.[0]?.id ||
        "";
      setSelectedProtocolId(proto);
    }
  }

  function handleDatasetChange(datasetId: string) {
    setSelectedDatasetId(datasetId);
    const ds = datasets.find((d) => d.id === datasetId);
    if (ds) {
      const proto =
        ds.default_protocol_id ||
        PROTOCOLS_BY_DATASET[datasetId]?.[0]?.id ||
        "";
      setSelectedProtocolId(proto);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setValidationError(null);
    setShortfallNotice(null);

    if (!selectedModelId) {
      setValidationError("Please select a foundation model.");
      return;
    }
    if (!selectedDatasetId) {
      setValidationError("Please select an evaluation dataset.");
      return;
    }
    if (sampleMode === "custom" && (!customSampleCount || customSampleCount < 1)) {
      setValidationError("Custom sample count must be at least 1.");
      return;
    }
    if (Number.isNaN(seed) || seed < 0) {
      setValidationError("Random seed must be a non-negative integer.");
      return;
    }

    setSubmitting(true);
    try {
      const run = await api.benchmarks.create({
        model_id: selectedModelId,
        dataset_id: selectedDatasetId,
        protocol_id: selectedProtocolId || undefined,
        split: activeDataset?.default_split,
        sample_size_mode: sampleMode,
        sample_count:
          sampleMode === "custom"
            ? customSampleCount
            : DEFAULT_SAMPLE_COUNTS[sampleMode],
        seed,
        is_private: isPrivate,
      });

      if (
        run.sample_selection &&
        typeof run.sample_selection === "object" &&
        "shortfall" in run.sample_selection &&
        Number(run.sample_selection.shortfall) > 0
      ) {
        setShortfallNotice(
          `Dataset shortfall: requested ${run.sample_selection.requested_samples} samples, but only ${run.sample_selection.actual_samples} were eligible. Shortfall of ${run.sample_selection.shortfall} recorded.`,
        );
      }

      router.push(`/benchmarks/${run.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setValidationError(
          "Authentication required to start a benchmark run. Please sign in first.",
        );
      } else {
        setValidationError(
          err instanceof Error
            ? err.message
            : "Failed to queue benchmark run",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <LoadingState message="Loading catalog definitions..." />;
  }

  if (pageError) {
    return (
      <div
        role="alert"
        aria-live="polite"
        className="rounded-xl border border-red-800/60 bg-red-950/40 p-6 text-red-200"
      >
        <h2 className="text-base font-semibold text-red-100">
          Catalog Initialization Error
        </h2>
        <p className="mt-1 text-sm text-red-300">{pageError}</p>
        <Link
          href="/dashboard"
          className="mt-4 inline-block text-xs font-medium text-red-300 underline"
        >
          Return to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl py-6">
      <div className="border-b border-zinc-800 pb-5">
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Configure Benchmark Run
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Run reproducible evaluations with deterministic sample selection and metric verification.
        </p>
      </div>

      {validationError && (
        <div
          role="alert"
          aria-live="polite"
          className="mt-6 rounded-md border border-red-800/60 bg-red-950/40 p-4 text-sm text-red-200"
        >
          <div className="font-semibold text-red-100">Configuration Error</div>
          <div className="mt-1">{validationError}</div>
          {validationError.includes("Authentication required") && (
            <div className="mt-3">
              <Link
                href="/login"
                className="rounded bg-red-900/60 px-3 py-1 text-xs font-medium text-white hover:bg-red-800"
              >
                Sign In Now
              </Link>
            </div>
          )}
        </div>
      )}

      {shortfallNotice && (
        <div
          role="status"
          aria-live="polite"
          className="mt-6 rounded-md border border-amber-800/60 bg-amber-950/40 p-4 text-sm text-amber-200"
        >
          <div className="font-semibold text-amber-100">Sampling Shortfall Report</div>
          <div className="mt-1">{shortfallNotice}</div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-8 space-y-6" noValidate>
        {/* Domain & Dataset */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 space-y-4">
          <h2 className="text-base font-semibold text-white">
            1. Evaluation Domain & Dataset
          </h2>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
                className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {domains.map((dom) => (
                  <option key={dom} value={dom}>
                    {dom}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="dataset-select"
                className="block text-xs font-medium text-zinc-300"
              >
                Dataset Suite
              </label>
              <select
                id="dataset-select"
                value={selectedDatasetId}
                onChange={(e) => handleDatasetChange(e.target.value)}
                className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {filteredDatasets.map((ds) => (
                  <option key={ds.id} value={ds.id}>
                    {ds.name} ({ds.id})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {availableProtocols.length > 0 && (
            <div>
              <label
                htmlFor="protocol-select"
                className="block text-xs font-medium text-zinc-300"
              >
                Evaluation Protocol
              </label>
              <select
                id="protocol-select"
                value={selectedProtocolId}
                onChange={(e) => setSelectedProtocolId(e.target.value)}
                className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {availableProtocols.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              {availableProtocols.find((p) => p.id === selectedProtocolId)?.description && (
                <p className="mt-1.5 text-xs text-zinc-400">
                  {availableProtocols.find((p) => p.id === selectedProtocolId)?.description}
                </p>
              )}
            </div>
          )}

          {activeDataset && (
            <div className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3 text-xs text-zinc-400">
              <span className="font-semibold text-zinc-300">Target Metrics:</span>{" "}
              {activeDataset.metrics?.join(", ") || activeDataset.evaluator_key} |{" "}
              <span className="font-semibold text-zinc-300">Default Split:</span>{" "}
              {activeDataset.default_split}
            </div>
          )}
        </div>

        {/* Model Selection */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 space-y-4">
          <h2 className="text-base font-semibold text-white">
            2. Target Foundation Model
          </h2>

          <div>
            <label
              htmlFor="model-select"
              className="block text-xs font-medium text-zinc-300"
            >
              Evaluated Model
            </label>
            <select
              id="model-select"
              value={selectedModelId}
              onChange={(e) => setSelectedModelId(e.target.value)}
              className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.hf_id}) — {m.torch_dtype}, {m.vram_weight_gb} GB VRAM
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Sampling & Seed */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 space-y-4">
          <h2 className="text-base font-semibold text-white">
            3. Sampling & Execution Parameters
          </h2>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="sample-mode-select"
                className="block text-xs font-medium text-zinc-300"
              >
                Sample Size Mode
              </label>
              <select
                id="sample-mode-select"
                value={sampleMode}
                onChange={(e) => setSampleMode(e.target.value)}
                className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="smoke">Smoke (10 samples, quick test)</option>
                <option value="pilot">Pilot (25 samples)</option>
                <option value="standard">Standard (100 samples)</option>
                <option value="full">Full Evaluation Split</option>
                <option value="custom">Custom Sample Count</option>
              </select>
            </div>

            {sampleMode === "custom" ? (
              <div>
                <label
                  htmlFor="custom-count"
                  className="block text-xs font-medium text-zinc-300"
                >
                  Exact Sample Count
                </label>
                <input
                  id="custom-count"
                  type="number"
                  min={1}
                  value={customSampleCount}
                  onChange={(e) => setCustomSampleCount(parseInt(e.target.value, 10) || 0)}
                  className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            ) : (
              <div>
                <label
                  htmlFor="seed-input"
                  className="block text-xs font-medium text-zinc-300"
                >
                  Deterministic Seed (SHA-256 Rule)
                </label>
                <input
                  id="seed-input"
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(parseInt(e.target.value, 10) || 0)}
                  className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 pt-2">
            <input
              id="is-private-checkbox"
              type="checkbox"
              checked={isPrivate}
              onChange={(e) => setIsPrivate(e.target.checked)}
              className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-indigo-600 focus:ring-indigo-500"
            />
            <label
              htmlFor="is-private-checkbox"
              className="text-xs text-zinc-300"
            >
              Keep benchmark private (visible only to your account)
            </label>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 pt-4">
          <Link
            href="/benchmarks"
            className="rounded-md border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-200 hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-zinc-500"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Submitting Benchmark..." : "Queue Benchmark"}
          </button>
        </div>
      </form>
    </div>
  );
}
