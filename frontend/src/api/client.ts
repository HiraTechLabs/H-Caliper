const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, message: string, code = "request_failed", details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type QueryValue = string | number | boolean | null | undefined;

export function buildQuery(params?: Record<string, QueryValue>): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const value = part.trim();
    if (value.startsWith(prefix)) return decodeURIComponent(value.slice(prefix.length));
  }
  return null;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...options.headers,
  };

  if (method !== "GET") {
    const token = readCookie("hcaliper_csrf");
    if (token) headers["X-CSRF-Token"] = token;
  }

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body,
      signal: options.signal,
      credentials: "include",
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "Cannot reach the H-Caliper API. Check that the backend is running.");
  }

  if (response.status === 204) return undefined as T;

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text();

  if (!response.ok) {
    const detail = (payload as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string") {
      throw new ApiError(response.status, detail, "request_failed", payload);
    }
    if (detail && typeof detail === "object") {
      const shape = detail as { message?: string; code?: string; errors?: unknown };
      throw new ApiError(
        response.status,
        shape.message ?? `Request failed (${response.status})`,
        shape.code ?? "request_failed",
        shape,
      );
    }
    throw new ApiError(response.status, `Request failed (${response.status})`, "request_failed", payload);
  }

  return payload as T;
}

export const api = {
  get<T>(path: string, params?: Record<string, QueryValue>, signal?: AbortSignal): Promise<T> {
    return request<T>(`${path}${buildQuery(params)}`, { signal });
  },
  post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, { method: "POST", body: body ?? {} });
  },
  put<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, { method: "PUT", body: body ?? {} });
  },
  patch<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, { method: "PATCH", body: body ?? {} });
  },
  delete<T = void>(path: string): Promise<T> {
    return request<T>(path, { method: "DELETE" });
  },
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) return error.message || "You do not have permission to do that.";
    if (error.status === 401) return "Your session has expired. Please sign in again.";
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
