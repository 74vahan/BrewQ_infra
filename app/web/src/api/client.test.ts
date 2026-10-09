import { afterEach, describe, expect, it, vi } from 'vitest';
import { request } from './client.ts';
import { ApiError } from './errors.ts';

function respond(status: number, body: string, contentType = 'application/json'): Response {
  return new Response(body, { status, headers: { 'Content-Type': contentType } });
}

function mockFetch(impl: (url: string, init: RequestInit) => Promise<Response>) {
  const fn = vi.fn(impl);
  vi.stubGlobal('fetch', fn);
  return fn;
}

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    if (error instanceof ApiError) return error;
    throw error;
  }
  throw new Error('expected the request to fail');
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('request', () => {
  it('returns parsed JSON on success and uses the /api base', async () => {
    const fetchMock = mockFetch(() => Promise.resolve(respond(200, '{"items":[1,2]}')));
    await expect(request<{ items: number[] }>('/barista/menu')).resolves.toEqual({ items: [1, 2] });
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/barista/menu');
  });

  it('sends the bearer token and never X-Device-Id', async () => {
    const fetchMock = mockFetch(() => Promise.resolve(respond(200, '{}')));
    await request('/barista/orders?scope=active', { token: 'abc' });
    const headers = fetchMock.mock.calls[0]?.[1].headers as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer abc');
    expect(Object.keys(headers).map((h) => h.toLowerCase())).not.toContain('x-device-id');
  });

  it('serialises a JSON body with a content type', async () => {
    const fetchMock = mockFetch(() => Promise.resolve(respond(200, '{}')));
    await request('/barista/login', { method: 'POST', body: { password: 'x' } });
    const init = fetchMock.mock.calls[0]?.[1];
    expect(init?.method).toBe('POST');
    expect(init?.body).toBe('{"password":"x"}');
    expect((init?.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  });

  it('parses the error envelope into an ApiError', async () => {
    mockFetch(() =>
      Promise.resolve(
        respond(
          409,
          '{"error":{"code":"INVALID_STATUS_TRANSITION","message":"x","details":{"from":"READY"}}}',
        ),
      ),
    );
    const error = await failure(request('/x'));
    expect(error.code).toBe('INVALID_STATUS_TRANSITION');
    expect(error.status).toBe(409);
    expect(error.details).toEqual({ from: 'READY' });
  });

  it('defaults details to an empty object when missing or not an object', async () => {
    mockFetch(() => Promise.resolve(respond(401, '{"error":{"code":"BARISTA_UNAUTHORIZED","details":[1]}}')));
    const error = await failure(request('/x'));
    expect(error.code).toBe('BARISTA_UNAUTHORIZED');
    expect(error.details).toEqual({});
  });

  it('maps an HTML error page (nginx 502) to UNKNOWN instead of crashing', async () => {
    mockFetch(() => Promise.resolve(respond(502, '<html>Bad Gateway</html>', 'text/html')));
    const error = await failure(request('/x'));
    expect(error.code).toBe('UNKNOWN');
    expect(error.status).toBe(502);
  });

  it('maps an empty error body to UNKNOWN', async () => {
    mockFetch(() => Promise.resolve(respond(504, '')));
    expect((await failure(request('/x'))).code).toBe('UNKNOWN');
  });

  it('maps a JSON error without an envelope to UNKNOWN', async () => {
    mockFetch(() => Promise.resolve(respond(500, '{"detail":"boom"}')));
    expect((await failure(request('/x'))).code).toBe('UNKNOWN');
  });

  it('keeps the meaning of a non-JSON 429', async () => {
    mockFetch(() => Promise.resolve(respond(429, '<html>Too Many Requests</html>', 'text/html')));
    expect((await failure(request('/x'))).code).toBe('RATE_LIMITED');
  });

  it('treats a 2xx that is not JSON as UNKNOWN', async () => {
    mockFetch(() => Promise.resolve(respond(200, '<html>portal</html>', 'text/html')));
    expect((await failure(request('/x'))).code).toBe('UNKNOWN');
  });

  it('maps a rejected fetch to NETWORK', async () => {
    mockFetch(() => Promise.reject(new TypeError('Failed to fetch')));
    const error = await failure(request('/x'));
    expect(error.code).toBe('NETWORK');
    expect(error.status).toBe(0);
  });

  it('rethrows the original error when the caller aborted', async () => {
    const controller = new AbortController();
    mockFetch(() => {
      controller.abort();
      return Promise.reject(new DOMException('aborted', 'AbortError'));
    });
    await expect(request('/x', { signal: controller.signal })).rejects.toMatchObject({
      name: 'AbortError',
    });
  });
});
