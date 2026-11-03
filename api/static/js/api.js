'use strict';

// Shared helpers for calling the API. Unlike a bare fetch(), these treat any
// non-2xx response or network failure as an error, carrying the server's message,
// so callers cannot mistake a failed request for a successful one.

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function errorDetailFrom(body, status) {
  const detail = body && body.detail;
  if (typeof detail === 'string') return detail;
  if (detail != null) return JSON.stringify(detail);
  return `Request failed (HTTP ${status})`;
}

// Resolves with the parsed JSON body (null for 204). Rejects with ApiError on any
// non-2xx response (status 0 when the server cannot be reached).
async function apiRequest(url, options = {}) {
  let resp;
  try {
    resp = await fetch(url, options);
  } catch (_) {
    throw new ApiError(0, 'Could not reach the server. Is the API running?');
  }
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new ApiError(resp.status, errorDetailFrom(body, resp.status));
  }
  if (resp.status === 204) return null;
  return resp.json();
}

function postJson(url, body) {
  return apiRequest(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

// ── Scenarios ─────────────────────────────────────────────────────────────

function scenarioUrl(name) {
  return `/api/scenarios/${encodeURIComponent(name)}`;
}

// Resolves with the scenario, or null when it does not exist (404). Any other
// failure rejects, so a transient error is never mistaken for "no scenario".
async function fetchScenarioOrNull(name) {
  try {
    return await apiRequest(scenarioUrl(name));
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

function saveScenarioFile(name, data) {
  return postJson(scenarioUrl(name), data);
}

function setCurrentScenarioName(name) {
  return postJson('/api/scenarios/current', { name });
}

function deleteScenarioFile(name) {
  return apiRequest(scenarioUrl(name), { method: 'DELETE' });
}
