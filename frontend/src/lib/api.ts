/**
 * EdgeErgo V3 — Standardized Frontend API Client.
 *
 * Implements native fetch wrapping with automatic Bearer token injection,
 * abort signal propagation, and standard error schema parsing.
 */

export interface ApiStandardError {
  code: string;
  message: string;
  request_id?: string;
}

export class ApiError extends Error {
  public code: string;
  public status: number;
  public requestId?: string;

  constructor(status: number, error: ApiStandardError) {
    super(error.message);
    this.name = "ApiError";
    this.status = status;
    this.code = error.code || "API_ERROR";
    this.requestId = error.request_id;
  }
}

export class ApiUnauthorizedError extends ApiError {
  constructor(error: ApiStandardError) {
    super(401, error);
    this.name = "ApiUnauthorizedError";
  }
}

export class ApiForbiddenError extends ApiError {
  constructor(error: ApiStandardError) {
    super(403, error);
    this.name = "ApiForbiddenError";
  }
}

export class ApiNetworkError extends Error {
  constructor(message = "Network connection failed. Please check your internet connection.") {
    super(message);
    this.name = "ApiNetworkError";
  }
}

import type { components } from "./api-types";

export type Schemas = components["schemas"];
export type UserProfileResponse = Schemas["UserMeResponse"];
export type MetricDefinition = Schemas["MetricDefinition"];
export type DashboardSummaryResponse = Schemas["DashboardSummaryResponse"];
export type DashboardTrendPoint = Schemas["DashboardTrendPoint"];
export type PostureBreakdown = Schemas["PostureBreakdown"];
export type IndicatorDistribution = Schemas["IndicatorDistribution"];
export type DeviceItem = Schemas["DeviceListItem"];
export type DeviceListItem = Schemas["DeviceListItem"];
export type TokenCreateRequest = Schemas["TokenCreateRequest"];
export type TokenCreateResponse = Schemas["TokenCreateResponse"];
export type DeviceRevokeResponse = Schemas["DeviceRevokeResponse"];
export type AssessmentListItem = Schemas["AssessmentListItem"];
export type AssessmentListResponse = Schemas["AssessmentListResponse"];
export type ReportScopePreviewResponse = Schemas["ReportScopePreviewResponse"];
export type AuditEventItem = Schemas["AuditEventItem"];
export type AuditListResponse = Schemas["AuditListResponse"];

export interface RequestOptions extends RequestInit {
  token?: string | null;
  onUnauthorized?: () => void;
}

/**
 * Resolves base API URL from environment.
 */
export function getApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === "string" && envUrl.trim() !== "") {
    return envUrl.replace(/\/+$/, "");
  }
  return "http://127.0.0.1:8000";
}

/**
 * Universal authenticated fetch wrapper.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;

  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");

  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  // Set Content-Type only for non-GET requests if not already specified
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    throw new ApiNetworkError();
  }

  // Parse response
  if (!response.ok) {
    let errorPayload: ApiStandardError = {
      code: "UNKNOWN_ERROR",
      message: `HTTP Error ${response.status}`,
    };

    try {
      const data = await response.json();
      if (data && data.error) {
        errorPayload = data.error;
      }
    } catch {
      // Body not JSON
    }

    if (response.status === 401) {
      if (options.onUnauthorized) {
        options.onUnauthorized();
      }
      throw new ApiUnauthorizedError(errorPayload);
    }

    if (response.status === 403) {
      throw new ApiForbiddenError(errorPayload);
    }

    throw new ApiError(response.status, errorPayload);
  }

  if (response.status === 204) {
    return undefined as unknown as T;
  }

  return (await response.json()) as T;
}

/**
 * Fetches the authenticated user's organization profile and role.
 */
export async function fetchMe(token: string, signal?: AbortSignal): Promise<UserProfileResponse> {
  return apiFetch<UserProfileResponse>("/api/v1/me", {
    token,
    signal,
  });
}

/**
 * Fetches dashboard summary and trend data.
 */
export async function fetchDashboardSummary(
  token: string,
  params?: {
    device_id?: string;
    from_date?: string;
    to_date?: string;
  },
  signal?: AbortSignal
): Promise<DashboardSummaryResponse> {
  const query = new URLSearchParams();
  if (params?.device_id) query.set("device_id", params.device_id);
  if (params?.from_date) query.set("from_date", params.from_date);
  if (params?.to_date) query.set("to_date", params.to_date);

  const qs = query.toString();
  return apiFetch<DashboardSummaryResponse>(`/api/v1/dashboard/summary${qs ? `?${qs}` : ""}`, {
    token,
    signal,
  });
}

/**
 * Fetches paginated organization assessments.
 */
export async function fetchAssessments(
  token: string,
  params?: {
    device_id?: string;
    from_date?: string;
    to_date?: string;
    validity?: string;
    scoring_version?: string;
    limit?: number;
    offset?: number;
  },
  signal?: AbortSignal
): Promise<AssessmentListResponse> {
  const query = new URLSearchParams();
  if (params?.device_id) query.set("device_id", params.device_id);
  if (params?.from_date) query.set("from_date", params.from_date);
  if (params?.to_date) query.set("to_date", params.to_date);
  if (params?.validity) query.set("validity", params.validity);
  if (params?.scoring_version) query.set("scoring_version", params.scoring_version);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));

  const qs = query.toString();
  return apiFetch<AssessmentListResponse>(`/api/v1/assessments${qs ? `?${qs}` : ""}`, {
    token,
    signal,
  });
}

/**
 * Fetches organization devices list.
 */
export async function fetchDevices(token: string, signal?: AbortSignal): Promise<DeviceListItem[]> {
  return apiFetch<DeviceListItem[]>("/api/v1/devices", {
    token,
    signal,
  });
}

/**
 * Creates a single-use device enrollment token (Admin only).
 */
export async function createEnrollmentToken(
  token: string,
  body: TokenCreateRequest,
  signal?: AbortSignal
): Promise<TokenCreateResponse> {
  return apiFetch<TokenCreateResponse>("/api/v1/devices/enrollment-tokens", {
    method: "POST",
    token,
    body: JSON.stringify(body),
    signal,
  });
}

/**
 * Revokes a device (Admin only).
 */
export async function revokeDevice(
  token: string,
  deviceId: string,
  signal?: AbortSignal
): Promise<DeviceRevokeResponse> {
  return apiFetch<DeviceRevokeResponse>(`/api/v1/devices/${deviceId}/revoke`, {
    method: "POST",
    token,
    signal,
  });
}

/**
 * Fetches scope preview for report export.
 */
export async function fetchReportPreview(
  token: string,
  params?: {
    device_id?: string;
    from_date?: string;
    to_date?: string;
    validity?: string;
  },
  signal?: AbortSignal
): Promise<ReportScopePreviewResponse> {
  const query = new URLSearchParams();
  if (params?.device_id) query.set("device_id", params.device_id);
  if (params?.from_date) query.set("from_date", params.from_date);
  if (params?.to_date) query.set("to_date", params.to_date);
  if (params?.validity) query.set("validity", params.validity);

  const qs = query.toString();
  return apiFetch<ReportScopePreviewResponse>(`/api/v1/reports/preview${qs ? `?${qs}` : ""}`, {
    token,
    signal,
  });
}

/**
 * Fetches audit log events.
 */
export async function fetchAuditEvents(
  token: string,
  params?: {
    target_id?: string;
    target_type?: string;
    action?: string;
    limit?: number;
    offset?: number;
  },
  signal?: AbortSignal
): Promise<AuditListResponse> {
  const query = new URLSearchParams();
  if (params?.target_id) query.set("target_id", params.target_id);
  if (params?.target_type) query.set("target_type", params.target_type);
  if (params?.action) query.set("action", params.action);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));

  const qs = query.toString();
  return apiFetch<AuditListResponse>(`/api/v1/audit-events${qs ? `?${qs}` : ""}`, {
    token,
    signal,
  });
}

/**
 * Authenticated CSV report download as Blob.
 */
export async function downloadAssessmentsCsv(
  token: string,
  params?: {
    device_id?: string;
    from_date?: string;
    to_date?: string;
    validity?: string;
  },
  signal?: AbortSignal
): Promise<Blob> {
  const baseUrl = getApiBaseUrl();
  const query = new URLSearchParams();
  if (params?.device_id) query.set("device_id", params.device_id);
  if (params?.from_date) query.set("from_date", params.from_date);
  if (params?.to_date) query.set("to_date", params.to_date);
  if (params?.validity) query.set("validity", params.validity);

  const qs = query.toString();
  const url = `${baseUrl}/api/v1/reports/export.csv${qs ? `?${qs}` : ""}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "text/csv, application/json",
      },
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    throw new ApiNetworkError();
  }

  if (!response.ok) {
    let errorPayload: ApiStandardError = {
      code: "EXPORT_FAILED",
      message: `Export failed with status ${response.status}`,
    };
    try {
      const data = await response.json();
      if (data && data.error) {
        errorPayload = data.error;
      }
    } catch {
      // Response not JSON
    }
    throw new ApiError(response.status, errorPayload);
  }

  return await response.blob();
}

/**
 * Helper to trigger a client-side download of a Blob.
 */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
