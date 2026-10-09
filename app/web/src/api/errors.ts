import type { ErrorDetails } from './types.ts';

/**
 * An API failure with the stable machine-readable `code`; the UI translates by
 * code and never shows the server's English `message`.
 */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: ErrorDetails;

  constructor(code: string, status: number, details: ErrorDetails = {}) {
    super(code);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

/** Anything thrown by a query or mutation, normalised to an ApiError. */
export function toApiError(error: unknown): ApiError {
  return error instanceof ApiError ? error : new ApiError('UNKNOWN', 0);
}
