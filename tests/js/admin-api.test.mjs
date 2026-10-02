import { afterEach, describe, expect, it, vi } from 'vitest';
import { createAdminClient } from '../../static/js/admin-api.js';

afterEach(() => vi.unstubAllGlobals());
const auth = { currentUser: { getIdToken: async () => 'test-token' } };

describe('Admin HTTP error contracts', () => {
  it.each([
    [{ error: { error_code: 'not_found', message: 'No account found.' } }, 'No account found.'],
    [{ detail: { error_code: 'conflict', message: 'Configuration changed in another session.' } }, 'Configuration changed in another session.'],
    [{ error: 'Admin privileges required' }, 'Admin privileges required'],
    [{ detail: 'Not found' }, 'Not found'],
    [{ detail: [{ msg: 'bad value', input: 'private-submitted-text' }] }, 'HTTP 409'],
    [{ error: { message: { raw: 'private-submitted-text' } } }, 'HTTP 409'],
    [null, 'HTTP 409'],
  ])('unpacks only allowed strings from %j', async (data, expected) => {
    const fetch = vi.fn(async () => ({ ok: false, status: 409, json: async () => data }));
    vi.stubGlobal('fetch', fetch);
    const request = createAdminClient(auth);
    await expect(request('PUT', '/api/admin/account-tier', { tier: 'plus' })).rejects.toThrow(expected);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'PUT', headers: { Authorization: 'Bearer test-token' }, body: '{"tier":"plus"}' });
  });

  it('preserves non-JSON status and never retries a write', async () => {
    const fetch = vi.fn(async () => ({ ok: false, status: 503, json: async () => { throw new SyntaxError('html'); } }));
    vi.stubGlobal('fetch', fetch);
    await expect(createAdminClient(auth)('POST', '/api/admin/models', {})).rejects.toThrow('HTTP 503');
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('does not request when logged out and returns a successful compact response', async () => {
    const fetch = vi.fn(async () => ({ ok: true, json: async () => ({ revision: 5 }) }));
    vi.stubGlobal('fetch', fetch);
    await expect(createAdminClient({ currentUser: null })('GET', '/api/admin/models')).rejects.toThrow('Not logged in');
    expect(fetch).not.toHaveBeenCalled();
    expect(await createAdminClient(auth)('GET', '/api/admin/models')).toEqual({ revision: 5 });
  });
});
