import { SETTINGS_STORAGE_KEY, useSettings } from "@/lib/store";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const PREFIX = "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
    public details: Record<string, unknown> = {},
    public requestId?: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Client errors (4xx) are deterministic; only network/5xx failures are worth retrying. */
  get retryable(): boolean {
    return this.status === 0 || this.status >= 500;
  }
}

type Params = Record<string, string | number | boolean | null | undefined>;

export function buildUrl(path: string, params?: Params): string {
  const url = new URL(`${API_URL}${path.startsWith("/api/") ? path : PREFIX + path}`);
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  }
  return url.toString();
}

interface RequestOptions {
  method?: "GET" | "POST" | "DELETE" | "PATCH";
  params?: Params;
  body?: unknown;
  form?: FormData;
  signal?: AbortSignal;
}

/** The key saved in this browser, read straight from storage. The settings store is rehydrated in an effect of <Providers/>, which runs
 * after the pages' first queries have already started; without this, every full page load sent its first requests without the key. */
function storedApiKey(): string {
  try {
    const raw = typeof window === "undefined" ? null : window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    const key = raw ? (JSON.parse(raw) as { state?: { apiKey?: unknown } })?.state?.apiKey : "";
    return typeof key === "string" ? key : "";
  } catch {
    return "";
  }
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const key = useSettings.getState().apiKey || (useSettings.persist.hasHydrated() ? "" : storedApiKey());
  if (key) headers["X-API-Key"] = key;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.params), { method: opts.method ?? "GET", headers, body, signal: opts.signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(`Cannot reach the backend at ${API_URL}. Is it running?`, 0, "network_error");
  }
  if (res.status === 204) return undefined as T;
  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const err = (payload as { error?: { code?: string; message?: string; details?: Record<string, unknown>; request_id?: string } } | null)?.error;
    throw new ApiError(err?.message ?? `Request failed (${res.status})`, res.status, err?.code ?? "http_error", err?.details, err?.request_id);
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string, params?: Params, signal?: AbortSignal) => request<T>(path, { params, signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", form }),
};
