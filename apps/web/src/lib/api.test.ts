import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiFetch } from './api';

beforeEach(() => {
  vi.resetAllMocks();
});

describe('apiFetch', () => {
  it('prefixes /api', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ok: true }),
    });
    const g = globalThis as unknown as { fetch: typeof fetch };
    g.fetch = mockFetch as typeof fetch;

    await apiFetch('/stories');
    expect(mockFetch).toHaveBeenCalledWith('/api/stories', undefined);
  });

  it('throws on http error', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({}),
    });
    const g = globalThis as unknown as { fetch: typeof fetch };
    g.fetch = mockFetch as typeof fetch;

    await expect(apiFetch('/fail')).rejects.toThrow('API request failed with 500');
  });
});
