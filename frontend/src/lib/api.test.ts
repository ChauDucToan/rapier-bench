import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, request } from "./api";

describe("api client and request helper", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("passes credentials: 'include' on all requests", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ status: "ok" }),
    });
    globalThis.fetch = mockFetch;

    await request("/api/v1/models");

    expect(mockFetch).toHaveBeenCalledOnce();
    const callArgs = mockFetch.mock.calls[0];
    expect(callArgs[1].credentials).toBe("include");
  });

  it("attaches X-Rapier-Action: 1 on mutation methods (POST, PUT, DELETE, PATCH)", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ id: "run-123" }),
    });
    globalThis.fetch = mockFetch;

    await api.benchmarks.cancel("run-123");

    expect(mockFetch).toHaveBeenCalledOnce();
    const headers = mockFetch.mock.calls[0][1].headers as Headers;
    expect(headers.get("X-Rapier-Action")).toBe("1");
    expect(mockFetch.mock.calls[0][1].method).toBe("POST");
  });

  it("does not attach X-Rapier-Action on GET requests", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => [],
    });
    globalThis.fetch = mockFetch;

    await api.models.list();

    const headers = mockFetch.mock.calls[0][1].headers as Headers;
    expect(headers.get("X-Rapier-Action")).toBeNull();
  });

  it("surfaces 401 unauthenticated state via ApiError", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Not authenticated" }),
    });
    globalThis.fetch = mockFetch;

    await expect(api.auth.me()).rejects.toThrowError(ApiError);

    try {
      await api.auth.me();
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(401);
      expect(apiErr.message).toBe("Not authenticated");
    }
  });

  it("surfaces 403 forbidden state via ApiError", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "CSRF token missing or non-owner access" }),
    });
    globalThis.fetch = mockFetch;

    await expect(api.benchmarks.cancel("run-999")).rejects.toThrowError(
      ApiError,
    );

    try {
      await api.benchmarks.cancel("run-999");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(403);
      expect(apiErr.message).toBe("CSRF token missing or non-owner access");
    }
  });

  it("surfaces 404 not found state via ApiError", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Benchmark run not found" }),
    });
    globalThis.fetch = mockFetch;

    try {
      await api.benchmarks.get("non-existent-id");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(404);
      expect(apiErr.message).toBe("Benchmark run not found");
    }
  });

  it("surfaces 500 server error state via ApiError", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      headers: new Headers({ "content-type": "text/plain" }),
      text: async () => "Internal Server Error",
    });
    globalThis.fetch = mockFetch;

    try {
      await api.models.get("any");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(500);
      expect(apiErr.message).toContain("Internal Server Error");
    }
  });
});
