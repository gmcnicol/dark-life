import { describe, it, expect, beforeEach, beforeAll, vi } from 'vitest';
import { NextRequest } from 'next/server';

const API_URL = 'https://api.example.com';

let rootGET: any;
let rootPOST: any;
let dynamicGET: any;

function mockResponse(body: string = '[]', status = 200) {
  return {
    status,
    headers: new Headers(),
    text: () => Promise.resolve(body),
  };
}

describe('stories API proxy routes', () => {
  beforeAll(async () => {
    process.env.API_BASE_URL = API_URL;
    ({ GET: rootGET, POST: rootPOST } = await import('./route'));
    ({ GET: dynamicGET } = await import('./[...path]/route'));
  });

  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('proxies root GET to API_BASE_URL', async () => {
    const mockFetch = vi.fn().mockResolvedValue(mockResponse());
    (globalThis as any).fetch = mockFetch;
    const req = new NextRequest('http://localhost/api/stories');
    await rootGET(req);
    expect(mockFetch).toHaveBeenCalledWith(`${API_URL}/stories`);
  });

  it('proxies root POST to API_BASE_URL', async () => {
    const mockFetch = vi.fn().mockResolvedValue(mockResponse('ok'));
    (globalThis as any).fetch = mockFetch;
    const req = new NextRequest('http://localhost/api/stories', { method: 'POST', body: '{}' });
    await rootPOST(req);
    expect(mockFetch).toHaveBeenCalledWith(
      `${API_URL}/stories`,
      expect.objectContaining({ method: 'POST', body: '{}' })
    );
  });

  it('proxies dynamic route to API_BASE_URL', async () => {
    const mockFetch = vi.fn().mockResolvedValue(mockResponse());
    (globalThis as any).fetch = mockFetch;
    const req = new NextRequest('http://localhost/api/stories/123');
    await dynamicGET(req, { params: { path: ['123'] } });
    expect(mockFetch).toHaveBeenCalledWith(
      `${API_URL}/stories/123`,
      expect.objectContaining({ method: 'GET', body: undefined })
    );
  });
});
