import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  apiFetch,
  fetchMe,
  ApiUnauthorizedError,
  ApiForbiddenError,
  ApiNetworkError,
} from "../lib/api";

describe("API Client (frontend/src/lib/api.ts)", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("injects Authorization Bearer header when token is supplied", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok" }),
    });
    global.fetch = mockFetch;

    const res = await apiFetch<{ status: string }>("/test", {
      token: "mock_jwt_token_123",
    });

    expect(res).toEqual({ status: "ok" });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/test"),
      expect.objectContaining({
        headers: expect.any(Headers),
      })
    );
    const call = mockFetch.mock.calls[0];
    const sentHeaders = (call?.[1]?.headers ?? new Headers()) as Headers;
    expect(sentHeaders.get("Authorization")).toBe("Bearer mock_jwt_token_123");
  });

  it("handles 401 Unauthorized by executing onUnauthorized callback and throwing ApiUnauthorizedError", async () => {
    const onUnauthorized = vi.fn();
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({
        error: { code: "UNAUTHORIZED", message: "Token expired", request_id: "req_123" },
      }),
    });

    await expect(
      apiFetch("/protected", { token: "expired_token", onUnauthorized })
    ).rejects.toThrow(ApiUnauthorizedError);

    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("handles 403 Forbidden by throwing ApiForbiddenError with standardized error payload", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({
        error: { code: "FORBIDDEN", message: "Admin privileges required", request_id: "req_456" },
      }),
    });

    try {
      await apiFetch("/admin/action", { token: "reviewer_token" });
      expect.unreachable("Should have thrown ApiForbiddenError");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiForbiddenError);
      const apiErr = err as ApiForbiddenError;
      expect(apiErr.status).toBe(403);
      expect(apiErr.code).toBe("FORBIDDEN");
      expect(apiErr.message).toBe("Admin privileges required");
      expect(apiErr.requestId).toBe("req_456");
    }
  });

  it("handles network failure by throwing ApiNetworkError", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Failed to fetch"));

    await expect(apiFetch("/any-path")).rejects.toThrow(ApiNetworkError);
  });

  it("handles request cancellation via AbortSignal without converting to ApiNetworkError", async () => {
    const controller = new AbortController();
    controller.abort();

    global.fetch = vi.fn().mockRejectedValue(new DOMException("The user aborted a request.", "AbortError"));

    await expect(apiFetch("/any-path", { signal: controller.signal })).rejects.toThrow(
      "The user aborted a request."
    );
  });

  it("fetchMe calls /api/v1/me and returns UserProfileResponse", async () => {
    const mockProfile = {
      user_id: "u123",
      email: "admin@corp.com",
      organization_id: "org123",
      organization_slug: "acme",
      role: "admin",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockProfile,
    });

    const profile = await fetchMe("valid_token");
    expect(profile).toEqual(mockProfile);
  });
});
