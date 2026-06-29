/**
 * Typed API client for the Pokémon AI backend (FastAPI).
 *
 * Endpoints already exposed by the backend:
 *   GET  /health
 *   GET  /metrics
 *   POST /move
 *   POST /evaluate
 *   POST /deck/analyze
 *   POST /deck/build
 *
 * Other UI surfaces (dashboard summary, training telemetry, benchmark
 * history, card database) consume mock services in `src/services/`
 * that can be swapped to real endpoints without changing components.
 */

const DEFAULT_BASE = "/api/backend"; // proxied through Next rewrite

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API ${status}`);
    this.status = status;
    this.body = body;
  }
}

export interface ApiClientOptions {
  baseUrl?: string;
  signal?: AbortSignal;
  retries?: number;
  retryDelayMs?: number;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  opts: ApiClientOptions = {},
): Promise<T> {
  const base = opts.baseUrl ?? DEFAULT_BASE;
  const url = `${base}${path}`;
  const retries = opts.retries ?? 1;
  let lastErr: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, {
        ...init,
        signal: opts.signal,
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          ...(init.headers ?? {}),
        },
      });
      const text = await res.text();
      const body = text ? safeJson(text) : null;
      if (!res.ok) throw new ApiError(res.status, body, `API error ${res.status}`);
      return body as T;
    } catch (err) {
      lastErr = err;
      if ((err as { name?: string }).name === "AbortError") throw err;
      if (attempt < retries) {
        await sleep((opts.retryDelayMs ?? 500) * Math.pow(2, attempt));
        continue;
      }
    }
  }
  throw lastErr;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export const api = {
  get: <T>(path: string, opts?: ApiClientOptions) =>
    request<T>(path, { method: "GET" }, opts),
  post: <T>(path: string, body: unknown, opts?: ApiClientOptions) =>
    request<T>(
      path,
      { method: "POST", body: body == null ? undefined : JSON.stringify(body) },
      opts,
    ),
};
