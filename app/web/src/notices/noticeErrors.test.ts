import { describe, expect, it } from 'vitest';
import { ApiError } from '../api/errors.ts';
import { reactToFailure } from './noticeErrors.ts';

describe('reactToFailure', () => {
  it('409 INVALID_STATUS_TRANSITION: refetch and say the order was already changed', () => {
    const reaction = reactToFailure(
      new ApiError('INVALID_STATUS_TRANSITION', 409, { from: 'READY', to: 'IN_PROGRESS' }),
    );
    expect(reaction).toEqual({
      messageKey: 'errors.INVALID_STATUS_TRANSITION',
      tone: 'warning',
      refetch: true,
      silent: false,
    });
  });

  it('404 ORDER_NOT_FOUND is treated like a lost race', () => {
    expect(reactToFailure(new ApiError('ORDER_NOT_FOUND', 404))).toMatchObject({ refetch: true, tone: 'warning' });
  });

  it('401 is silent: the router sends the barista to sign in', () => {
    expect(reactToFailure(new ApiError('BARISTA_UNAUTHORIZED', 401))).toMatchObject({ silent: true });
  });

  it('429, network and server errors show their message without refetching', () => {
    for (const code of ['RATE_LIMITED', 'NETWORK', 'INTERNAL_ERROR']) {
      expect(reactToFailure(new ApiError(code, 0))).toEqual({
        messageKey: `errors.${code}`,
        tone: 'error',
        refetch: false,
        silent: false,
      });
    }
  });

  it('anything that is not an ApiError, or has an unknown code, gets the generic message', () => {
    expect(reactToFailure(new Error('boom')).messageKey).toBe('errors.UNKNOWN');
    expect(reactToFailure(new ApiError('SOMETHING_NEW', 418)).messageKey).toBe('errors.UNKNOWN');
  });
});
