import type {
  BenchmarkRunResponse,
  ComparisonResponse,
  CreateBenchmarkRequest,
  DatasetResponse,
  LeaderboardResponse,
  LoginRequest,
  ModelResponse,
  PaginatedPredictionsResponse,
  PaginatedRunsResponse,
  RecommendationRequest,
  RecommendationResponse,
  RegisterRequest,
  RunResultsResponse,
  RunStatusResponse,
  UserResponse,
} from "@/types/api";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown, message?: string) {
    let msg = message;
    if (!msg && body && typeof body === "object" && "detail" in body) {
      const detail = body.detail;
      if (typeof detail === "string") {
        msg = detail;
      } else if (Array.isArray(detail)) {
        msg = detail
          .map((d) => {
            if (d && typeof d === "object" && "msg" in d) {
              const loc = "loc" in d && Array.isArray(d.loc) ? d.loc.join(".") : "";
              return loc ? `${loc}: ${String(d.msg)}` : String(d.msg);
            }
            return JSON.stringify(d);
          })
          .join("; ");
      }
    }
    super(msg ?? `API error: ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const MUTATION_METHODS: Record<string, true> = {
  POST: true,
  PUT: true,
  DELETE: true,
  PATCH: true,
};

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith("http")
    ? path
    : `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;

  const method = (init?.method ?? "GET").toUpperCase();
  const headers = new Headers(init?.headers);

  if (MUTATION_METHODS[method]) {
    headers.set("X-Rapier-Action", "1");
  }

  if (
    !headers.has("Content-Type") &&
    init?.body &&
    typeof init.body === "string"
  ) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(url, {
    ...init,
    method,
    credentials: "include",
    headers,
  });

  const contentType = res.headers.get("content-type");
  const isJson = contentType?.includes("application/json");
  const body = isJson
    ? await res.json().catch(() => null)
    : await res.text().catch(() => null);

  if (!res.ok) {
    throw new ApiError(
      res.status,
      body,
      typeof body === "string" ? body : undefined,
    );
  }

  return body as T;
}

function toQueryString(params?: Record<string, string | number | boolean | undefined | null>): string {
  if (!params) return "";
  const searchParams = new URLSearchParams();
  for (const [key, val] of Object.entries(params)) {
    if (val !== undefined && val !== null && val !== "") {
      searchParams.set(key, String(val));
    }
  }
  const str = searchParams.toString();
  return str ? `?${str}` : "";
}

export const api = {
  auth: {
    register: (body: RegisterRequest) =>
      request<UserResponse>("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    login: (body: LoginRequest) =>
      request<UserResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    logout: () =>
      request<{ status: string }>("/api/v1/auth/logout", {
        method: "POST",
      }),
    me: () => request<UserResponse>("/api/v1/auth/me"),
  },
  models: {
    list: (params?: { domain?: string; limit?: number; offset?: number }) =>
      request<ModelResponse[]>(`/api/v1/models${toQueryString(params)}`),
    get: (id: string) => request<ModelResponse>(`/api/v1/models/${encodeURIComponent(id)}`),
  },
  datasets: {
    list: (params?: { domain?: string; limit?: number; offset?: number }) =>
      request<DatasetResponse[]>(`/api/v1/datasets${toQueryString(params)}`),
    get: (id: string) => request<DatasetResponse>(`/api/v1/datasets/${encodeURIComponent(id)}`),
  },
  benchmarks: {
    create: (body: CreateBenchmarkRequest) =>
      request<BenchmarkRunResponse>("/api/v1/benchmarks", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    list: (params?: {
      model_id?: string;
      domain?: string;
      status?: string;
      limit?: number;
      offset?: number;
    }) =>
      request<PaginatedRunsResponse>(`/api/v1/benchmarks${toQueryString(params)}`),
    get: (id: string) =>
      request<BenchmarkRunResponse>(`/api/v1/benchmarks/${encodeURIComponent(id)}`),
    getStatus: (id: string) =>
      request<RunStatusResponse>(`/api/v1/benchmarks/${encodeURIComponent(id)}/status`),
    getResults: (id: string) =>
      request<RunResultsResponse>(`/api/v1/benchmarks/${encodeURIComponent(id)}/results`),
    getPredictions: (
      id: string,
      params?: { status?: string; limit?: number; offset?: number },
    ) =>
      request<PaginatedPredictionsResponse>(
        `/api/v1/benchmarks/${encodeURIComponent(id)}/predictions${toQueryString(params)}`,
      ),
    cancel: (id: string) =>
      request<RunStatusResponse>(`/api/v1/benchmarks/${encodeURIComponent(id)}/cancel`, {
        method: "POST",
      }),
    rerun: (id: string) =>
      request<BenchmarkRunResponse>(`/api/v1/benchmarks/${encodeURIComponent(id)}/rerun`, {
        method: "POST",
      }),
    getExportUrl: (id: string, format: "jsonl" | "csv" = "jsonl") =>
      `${API_BASE}/api/v1/benchmarks/${encodeURIComponent(id)}/export?format=${format}`,
  },
  comparisons: {
    get: (runIds: string[]) =>
      request<ComparisonResponse>(`/api/v1/comparisons?run_ids=${encodeURIComponent(runIds.join(","))}`),
  },
  leaderboard: {
    get: (params?: { domain?: string; task_type?: string }) =>
      request<LeaderboardResponse>(`/api/v1/leaderboard${toQueryString(params)}`),
  },
  recommendations: {
    create: (body: RecommendationRequest) =>
      request<RecommendationResponse>("/api/v1/recommendations", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },
} as const;
