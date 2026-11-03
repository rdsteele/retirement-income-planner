// Tests for api/static/js/api.js

test('apiRequest resolves with the parsed body on 200', async () => {
  const server = new FakeServer();
  server.handle('GET', '/x', () => ({ status: 200, body: { ok: 1 } }));
  assertEqual(await apiRequest('/x'), { ok: 1 });
});

test('apiRequest resolves null on 204', async () => {
  const server = new FakeServer();
  server.handle('DELETE', '/x', () => ({ status: 204, body: null }));
  assertEqual(await apiRequest('/x', { method: 'DELETE' }), null);
});

test('apiRequest rejects with an ApiError carrying the server detail and status', async () => {
  const server = new FakeServer();
  server.failOn('GET', '/x', 500);
  await assertRejects(
    apiRequest('/x'),
    (e) => e instanceof ApiError && e.message === 'disk full' && e.status === 500,
  );
});

test('apiRequest stringifies a list-shaped detail', async () => {
  const server = new FakeServer();
  server.handle('GET', '/x', () => ({ status: 422, body: { detail: [{ msg: 'bad' }] } }));
  await assertRejects(apiRequest('/x'), (e) => e.message === '[{"msg":"bad"}]');
});

test('apiRequest falls back to the HTTP status when the error body is not JSON', async () => {
  globalThis.fetch = () => Promise.resolve(fakeResponse(502, null, true));
  await assertRejects(apiRequest('/x'), (e) => e.message === 'Request failed (HTTP 502)');
});

test('apiRequest turns a network failure into an ApiError with status 0', async () => {
  const server = new FakeServer();
  server.failOn('GET', '/x', 0);
  await assertRejects(
    apiRequest('/x'),
    (e) => e instanceof ApiError && e.status === 0 && /Could not reach the server/.test(e.message),
  );
});

test('postJson sends a JSON POST', async () => {
  const server = new FakeServer();
  server.handle('POST', '/p', () => ({ status: 200, body: {} }));
  await postJson('/p', { a: 1 });
  assertEqual(server.calls[0], { method: 'POST', url: '/p', body: { a: 1 } });
});

test('scenario URLs encode the name', async () => {
  const server = makeScenarioServer();
  await fetchScenarioOrNull('2026 Base/Plan');
  assertEqual(server.calls[0].url, '/api/scenarios/2026 Base/Plan');
  assertEqual(scenarioUrl('2026 Base/Plan'), '/api/scenarios/2026%20Base%2FPlan');
});

test('fetchScenarioOrNull returns null only for a 404', async () => {
  makeScenarioServer();
  assertEqual(await fetchScenarioOrNull('missing'), null);
});

test('fetchScenarioOrNull rejects on a server error (not mistaken for missing)', async () => {
  const server = makeScenarioServer();
  server.failOn('GET', '/api/scenarios/x', 500);
  await assertRejects(fetchScenarioOrNull('x'), (e) => e.status === 500);
});

test('fetchScenarioOrNull rejects on a network failure', async () => {
  const server = makeScenarioServer();
  server.failOn('GET', '/api/scenarios/x', 0);
  await assertRejects(fetchScenarioOrNull('x'), (e) => e.status === 0);
});

test('saveScenarioFile and setCurrentScenarioName post to the right endpoints', async () => {
  const server = makeScenarioServer();
  await saveScenarioFile('P', { v: 1 });
  await setCurrentScenarioName('P');
  await setCurrentScenarioName(null);
  assertEqual(server.scenarios.P, { v: 1 });
  assertEqual(server.callsMatching('POST', '/api/scenarios/current').map((c) => c.body), [
    { name: 'P' },
    { name: null },
  ]);
});

test('deleteScenarioFile resolves null on success and rejects with the detail on failure', async () => {
  const server = makeScenarioServer();
  server.scenarios.P = { name: 'P' };
  assertEqual(await deleteScenarioFile('P'), null);
  await assertRejects(deleteScenarioFile('P'), (e) => e.message === 'Scenario not found: P');
});
