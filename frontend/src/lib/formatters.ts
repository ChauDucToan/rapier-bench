const PERCENTAGE_METRICS: Record<string, true> = {
  accuracy: true,
  invalid_parsed_rate: true,
  micro_f1: true,
  micro_precision: true,
  micro_recall: true,
  json_validity_rate: true,
  missing_attr_rate: true,
  unsupported_attr_rate: true,
  parse_failure_rate: true,
  balanced_accuracy: true,
  yes_recall: true,
  no_recall: true,
  aggregate_macro_balanced_accuracy: true,
  prompt_level_strict_acc: true,
  prompt_level_loose_acc: true,
  inst_level_strict_acc: true,
  inst_level_loose_acc: true,
  unanswerable_context_accuracy: true,
  answerable_control_accuracy: true,
  balanced_score: true,
  quality_score: true,
  normalized_quality: true,
  normalized_latency: true,
  normalized_vram: true,
  composite_score: true,
};

const COUNT_METRICS: Record<string, true> = {
  nn_count: true,
  nv_count: true,
  vn_count: true,
  vc_count: true,
  vw_count: true,
  sample_count: true,
  input_tokens: true,
  output_tokens: true,
  progress_done: true,
  progress_total: true,
  parameters: true,
  total: true,
  eligible_count: true,
};

export function isPercentageMetric(key: string): boolean {
  if (PERCENTAGE_METRICS[key]) return true;
  return (
    key.endsWith("_acc") ||
    key.endsWith("_rate") ||
    key.endsWith("_f1") ||
    key.endsWith("_precision") ||
    key.endsWith("_recall") ||
    key.endsWith("_score")
  );
}

export function isCountMetric(key: string): boolean {
  if (COUNT_METRICS[key]) return true;
  return key.endsWith("_count") || key.endsWith("_tokens");
}

export function formatMetricValue(
  key: string,
  value: number | null | undefined,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  if (isPercentageMetric(key)) {
    // If metric is between 0 and 1, multiply by 100 for display
    const pct = value <= 1.0 && value >= 0.0 ? value * 100 : value;
    return `${pct.toFixed(1)}%`;
  }

  if (isCountMetric(key)) {
    return Math.round(value).toLocaleString();
  }

  if (key.includes("latency") || key.endsWith("_ms")) {
    return `${value.toFixed(1)} ms`;
  }

  if (key.includes("vram") || key.endsWith("_gb")) {
    return `${value.toFixed(2)} GB`;
  }

  return Number.isInteger(value) ? value.toString() : value.toFixed(3);
}

const METRIC_LABELS: Record<string, string> = {
  accuracy: "Accuracy",
  invalid_parsed_rate: "Invalid Parse Rate",
  micro_f1: "Micro F1",
  micro_precision: "Micro Precision",
  micro_recall: "Micro Recall",
  json_validity_rate: "JSON Validity Rate",
  missing_attr_rate: "Missing Attr Rate",
  unsupported_attr_rate: "Unsupported Attr Rate",
  parse_failure_rate: "Parse Failure Rate",
  balanced_accuracy: "Balanced Accuracy",
  yes_recall: "Yes Recall",
  no_recall: "No Recall",
  aggregate_macro_balanced_accuracy: "Macro Balanced Acc",
  prompt_level_strict_acc: "Strict Prompt Acc",
  prompt_level_loose_acc: "Loose Prompt Acc",
  inst_level_strict_acc: "Strict Inst Acc",
  inst_level_loose_acc: "Loose Inst Acc",
  unanswerable_context_accuracy: "Unanswerable Acc",
  answerable_control_accuracy: "Control Acc",
  balanced_score: "Balanced Score",
  nn_count: "NN (Null-Null)",
  nv_count: "NV (Null-Val)",
  vn_count: "VN (Val-Null)",
  vc_count: "VC (Val-Correct)",
  vw_count: "VW (Val-Wrong)",
  latency_ms: "Latency",
  avg_latency_ms: "Avg Latency",
  vram_weight_gb: "VRAM Weight",
  composite_score: "Composite Score",
};

export function formatMetricName(key: string): string {
  if (METRIC_LABELS[key]) {
    return METRIC_LABELS[key];
  }
  return key
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function formatParameters(params: number): string {
  if (!params || params <= 0) return "—";
  if (params >= 1e9) {
    return `${(params / 1e9).toFixed(1)}B`;
  }
  if (params >= 1e6) {
    return `${(params / 1e6).toFixed(0)}M`;
  }
  return params.toLocaleString();
}

export function formatVram(gb: number | null | undefined): string {
  if (gb === null || gb === undefined) return "—";
  return `${gb.toFixed(2)} GB`;
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  return `${ms.toFixed(1)} ms`;
}

export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  try {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return isoString;
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}
