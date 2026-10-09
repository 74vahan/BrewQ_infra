import { ApiError } from './errors.ts';
import type { ErrorDetails } from './types.ts';

/**
 * Thin fetch wrapper around the REST API (memory/03-api.md).
 *
 * - Same origin: nginx serves the panel and proxies /api, Vite proxies in dev.
 * - Error envelope `{"error":{"code","message","details"}}` is parsed into an
 *   ApiError; anything that is not an envelope (nginx HTML pages, empty
 *   bodies) becomes `UNKNOWN` instead of crashing.
 * - The panel never sends `X-Device-Id`; the barista token goes in `Authorization`.
 */

const BASE = '/api';
const TIMEOUT_MS = 15_000;

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH';
  body?: unknown;
  token?: string | null | undefined;
  signal?: AbortSignal | undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Pulls `{code, details}` out of an error envelope, or null if it is not one. */
function readEnvelope(payload: unknown): { code: string; details: ErrorDetails } | null {
  if (!isRecord(payload)) return null;
  const error = payload['error'];
  if (!isRecord(error)) return null;
  const code = error['code'];
  if (typeof code !== 'string' || code === '') return null;
  const details = error['details'];
  return { code, details: isRecord(details) ? details : {} };
}

function parseJson(text: string): unknown {
  if (text === '') return undefined;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return undefined;
  }
}

function buildSignal(callerSignal: AbortSignal | undefined): AbortSignal {
  const timeout = AbortSignal.timeout(TIMEOUT_MS);
  return callerSignal ? AbortSignal.any([callerSignal, timeout]) : timeout;
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (options.token) headers['Authorization'] = `Bearer ${options.token}`;

  try {
    return await fetch(`${BASE}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? null : JSON.stringify(options.body),
      signal: buildSignal(options.signal),
    });
  } catch (error) {
    // The caller aborting (unmount, query cancel) is not a failure to show.
    if (options.signal?.aborted) throw error;
    throw new ApiError('NETWORK', 0);
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(path, options);

  let text: string;
  try {
    text = await response.text();
  } catch {
    throw new ApiError('NETWORK', response.status);
  }
  const payload = parseJson(text);

  if (!response.ok) {
    const envelope = readEnvelope(payload);
    if (envelope) throw new ApiError(envelope.code, response.status, envelope.details);
    // nginx may answer 429 with a non-JSON page; the meaning is still known.
    if (response.status === 429) throw new ApiError('RATE_LIMITED', 429);
    throw new ApiError('UNKNOWN', response.status);
  }

  // A 2xx that is not JSON (proxy landing page, captive portal) is not our API.
  if (payload === undefined) throw new ApiError('UNKNOWN', response.status);
  return payload as T;
}
