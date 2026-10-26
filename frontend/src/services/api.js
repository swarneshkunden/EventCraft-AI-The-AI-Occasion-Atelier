/**
 * API client – thin wrapper around fetch.
 * Credentials (httpOnly cookies) sent automatically.
 * Never exposes raw errors to the UI.
 */

const BASE = '';  // Same origin
let pendingMutations = 0;

export function hasPendingMutations() {
  return pendingMutations > 0;
}

export class ApiError extends Error {
  constructor(message, status, requestId, retryAfter = null) {
    super(message);
    this.status = status;
    this.requestId = requestId;
    this.retryAfter = retryAfter;
  }
}

async function request(method, path, body, isFormData = false) {
  const headers = {};
  if (body && !isFormData) {
    headers['Content-Type'] = 'application/json';
  }

  const opts = {
    method,
    headers,
    credentials: 'same-origin',
    cache: 'no-store',
  };

  if (body) {
    opts.body = isFormData ? body : JSON.stringify(body);
  }

  let resp;
  const isMutation = !['GET', 'HEAD', 'OPTIONS'].includes(method);
  if (isMutation) pendingMutations++;
  try {
    resp = await fetch(BASE + path, opts);
  } catch (err) {
    throw new ApiError('Network error. Please check your connection.', 0, null);
  } finally {
    if (isMutation) pendingMutations--;
  }

  let data;
  const contentType = resp.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    data = await resp.json();
  } else {
    data = { detail: await resp.text() };
  }

  if (!resp.ok) {
    const msg = data.detail || 'Something went wrong.';
    const retryAfterHeader = resp.headers.get('retry-after');
    const retryAfter = retryAfterHeader && Number.isFinite(Number(retryAfterHeader))
      ? Number(retryAfterHeader)
      : null;
    throw new ApiError(msg, resp.status, resp.headers.get('x-request-id'), retryAfter);
  }

  return data;
}

export const api = {
  get:    (path)          => request('GET',    path),
  post:   (path, body)    => request('POST',   path, body),
  put:    (path, body)    => request('PUT',    path, body),
  patch:  (path, body)    => request('PATCH',  path, body),
  delete: (path)          => request('DELETE', path),
  upload: (path, formData) => request('POST',  path, formData, true),
};
