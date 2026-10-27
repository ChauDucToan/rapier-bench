export type RunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface UserResponse {
  id: number;
  username: string;
  email: string;
  created_at: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  email?: string;
  username?: string;
  password: string;
}

export interface ModelResponse {
  id: string;
  name: string;
  hf_id: string;
  revision: string;
  parameters: number;
  context_length: number;
  torch_dtype: string;
  vram_weight_gb: number;
  trust_remote_code: boolean;
  license: string;
}

export interface DatasetResponse {
  id: string;
  name: string;
  hf_id: string;
  domain: string;
  task_type: string;
  default_split: string;
  evaluator_key: string;
}

export interface CreateBenchmarkRequest {
  model_id: string;
  dataset_id: string;
  protocol_id?: string | null;
  split?: string | null;
  sample_size_mode?: "smoke" | "pilot" | "standard" | "full" | "custom" | string;
  sample_count?: number | null;
  seed?: number;
  is_private?: boolean;
}

export interface ShortfallReport {
  requested_samples?: number;
  actual_samples?: number;
  shortfall?: number;
  [key: string]: unknown;
}

export interface BenchmarkRunResponse {
  id: string;
  user_id: number;
  model_id: string;
  dataset_id: string;
  protocol_id: string;
  split: string;
  sample_size_mode: string;
  sample_count: number | null;
  seed: number;
  status: RunStatus;
  is_private: boolean;
  cancel_requested: boolean;
  progress_done: number;
  progress_total: number;
  error_text?: string | null;
  sample_selection?: ShortfallReport | null;
  hardware_metadata?: Record<string, unknown> | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface PaginatedRunsResponse {
  items: BenchmarkRunResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface RunStatusResponse {
  id: string;
  status: RunStatus;
  progress_done: number;
  progress_total: number;
  cancel_requested: boolean;
  error_text?: string | null;
}

export interface RunResultsResponse {
  run_id: string;
  status: RunStatus;
  metrics: Record<string, number>;
  hardware_metadata?: Record<string, unknown> | null;
  sample_selection?: ShortfallReport | null;
  artifacts?: Array<Record<string, unknown>>;
}

export interface PredictionRecord {
  sample_id: string;
  model_id?: string;
  model_revision?: string;
  protocol_version?: string;
  prompt_hash?: string;
  raw_output?: string;
  parsed_output?: string | Record<string, unknown> | null;
  parse_status?: string;
  parse_error?: string | null;
  input_tokens?: number;
  output_tokens?: number;
  latency_ms?: number;
  error?: string | null;
  target?: string | Record<string, unknown> | null;
  is_correct?: boolean | null;
  [key: string]: unknown;
}

export interface PaginatedPredictionsResponse {
  items: PredictionRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface ComparisonResponse {
  runs: BenchmarkRunResponse[];
  metrics_comparison: Record<string, Record<string, number>>;
  diffs?: Record<string, unknown>;
}

export interface LeaderboardItem {
  model_id: string;
  model_name: string;
  domain: string;
  task_type: string;
  dataset_id?: string | null;
  primary_metric_name: string;
  primary_metric_value: number;
  avg_latency_ms?: number | null;
  vram_weight_gb?: number | null;
  run_id: string;
  sample_count?: number | null;
  completed_at?: string | null;
}

export interface LeaderboardGroup {
  dataset_id: string;
  protocol_id: string;
  split: string;
  sample_count?: number | null;
  primary_metric_name: string;
  cohort_id?: string;
  items: LeaderboardItem[];
}

export interface LeaderboardResponse {
  domain?: string | null;
  task_type?: string | null;
  groups: LeaderboardGroup[];
  items: LeaderboardItem[];
  total: number;
}

export interface RecommendationConstraints {
  max_vram_gb?: number | null;
  max_latency_ms?: number | null;
  min_quality?: number | null;
}

export interface RecommendationWeights {
  quality: number;
  latency: number;
  vram: number;
}

export interface RecommendationRequest {
  domain: string;
  task_type?: string | null;
  constraints?: RecommendationConstraints | null;
  weights?: RecommendationWeights | null;
}

export interface RecommendationModelBreakdown {
  model_id: string;
  model_name: string;
  composite_score: number;
  quality_score: number;
  latency_ms: number;
  vram_gb: number;
  normalized_quality: number;
  normalized_latency: number;
  normalized_vram: number;
  run_id: string;
}

export interface RecommendationResponse {
  status: "ok" | "insufficient_sample" | string;
  domain: string;
  task_type?: string | null;
  recommendations: RecommendationModelBreakdown[];
  eligible_count: number;
  limitations: string[];
  explanation: string;
}
