// Tests for api/static/js/scenario-bar.js

// What a page hands the shared save code: its shared inputs and page-specific sections.
function gatherStub() {
  return {
    shared: { inputs: { tax_year: 2031, filing_status: 'beta' }, aca: { include_aca: true }, ohio: {} },
    page: { emr_settings: { sweep: 1 } },
  };
}

function barSetup(configure, pageOptions) {
  installFakePage(pageOptions);
  const timers = installFakeTimers();
  const server = makeScenarioServer();
  currentScenarioName = null;
  if (configure) configure(server);
  return { server, timers };
}

const status = () => el('scenario-status');

// ── Bar and status ────────────────────────────────────────────────────────

test('updateScenarioBar shows the name, or a placeholder when none is loaded', () => {
  barSetup();
  currentScenarioName = 'Plan A';
  updateScenarioBar();
  assertEqual(el('scenario-name-display').textContent, '📋 Plan A');
  currentScenarioName = null;
  updateScenarioBar();
  assertEqual(el('scenario-name-display').textContent, '📋 No scenario loaded');
});

test('updateScenarioBar enables Save only when a scenario is loaded', () => {
  barSetup();
  currentScenarioName = 'Plan A';
  updateScenarioBar();
  assertEqual(el('save-btn').disabled, false);
  currentScenarioName = null;
  updateScenarioBar();
  assertEqual(el('save-btn').disabled, true);
});

test('setScenarioStatus: a success message fades, an error stays', () => {
  const { timers } = barSetup();
  setScenarioStatus('Saved "A"');
  assertTrue(status().className.indexOf('ok') !== -1);
  timers.runPending();
  assertEqual(status().textContent, '');
  setScenarioStatus('Could not save', true);
  assertTrue(status().className.indexOf('error') !== -1);
  timers.runPending();
  assertEqual(status().textContent, 'Could not save');
});

// ── Scenario file builders ────────────────────────────────────────────────

test('newEmptyScenario has every section and the format version', () => {
  const scenario = newEmptyScenario('Fresh');
  assertEqual(scenario.name, 'Fresh');
  assertEqual(scenario.version, SCENARIO_FORMAT_VERSION);
  assertEqual(
    ['inputs', 'ohio', 'aca', 'emr_settings', 'income_planning'].map((k) => scenario[k]),
    [{}, {}, {}, {}, {}],
  );
  assertTrue(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(scenario.saved_at), scenario.saved_at);
});

test('buildScenarioData merges the page inputs into the existing scenario', () => {
  const existing = {
    name: 'Old', keep: 'other-page-data',
    inputs: { pension: 1, tax_year: 1999 }, aca: { old: true }, ohio: { old: true },
    income_planning: { stays: 1 },
  };
  const data = buildScenarioData('Plan A', existing, gatherStub());
  assertEqual(data.name, 'Plan A');
  assertEqual(data.keep, 'other-page-data');
  assertEqual(data.inputs, { pension: 1, tax_year: 2031, filing_status: 'beta' });
  assertEqual(data.aca, { old: true, include_aca: true });
  assertEqual(data.ohio, { old: true });
  assertEqual(data.emr_settings, { sweep: 1 });
  assertEqual(data.income_planning, { stays: 1 });
  assertEqual(data.version, SCENARIO_FORMAT_VERSION);
});

// ── Loading the current scenario ──────────────────────────────────────────

test('loadCurrentScenario: populates the page from the loaded scenario', async () => {
  const { server } = barSetup((s) => {
    s.current = 'Plan A';
    s.scenarios['Plan A'] = { name: 'Plan A' };
  });
  const calls = [];
  const ok = await loadCurrentScenario((scenario, name) => calls.push([scenario.name, name]));
  assertEqual([ok, calls, currentScenarioName], [true, [['Plan A', 'Plan A']], 'Plan A']);
  assertEqual(el('scenario-name-display').textContent, '📋 Plan A');
  assertEqual(server.callsMatching('GET', '/api/scenarios/current').length, 1);
});

test('loadCurrentScenario: awaits an async populate callback', async () => {
  barSetup((s) => {
    s.current = 'Plan A';
    s.scenarios['Plan A'] = { name: 'Plan A' };
  });
  let finished = false;
  await loadCurrentScenario(async () => {
    await settle();
    finished = true;
  });
  assertTrue(finished, 'populate was not awaited');
});

test('loadCurrentScenario: no current scenario is success and populates nothing', async () => {
  barSetup();
  let called = false;
  const ok = await loadCurrentScenario(() => { called = true; });
  assertEqual([ok, called, status().textContent], [true, false, '']);
});

test('loadCurrentScenario: a missing scenario file clears the name and reports it', async () => {
  barSetup((s) => { s.current = 'Plan A'; });
  let called = false;
  const ok = await loadCurrentScenario(() => { called = true; });
  assertEqual([ok, called, currentScenarioName], [false, false, null]);
  assertTrue(/Could not load "Plan A"/.test(status().textContent), status().textContent);
  assertTrue(status().className.indexOf('error') !== -1);
  assertEqual(el('scenario-name-display').textContent, '📋 No scenario loaded');
});

test('loadCurrentScenario: a server error clears the name so Save cannot overwrite with a blank form', async () => {
  barSetup((s) => {
    s.current = 'Plan A';
    s.scenarios['Plan A'] = { name: 'Plan A' };
    s.failOn('GET', '/api/scenarios/Plan', 500);
  });
  const ok = await loadCurrentScenario(() => {});
  assertEqual([ok, currentScenarioName], [false, null]);
  assertTrue(/Could not load "Plan A": disk full/.test(status().textContent), status().textContent);
});

test('loadCurrentScenario: a failing populate callback is reported and clears the name', async () => {
  barSetup((s) => {
    s.current = 'Plan A';
    s.scenarios['Plan A'] = { name: 'Plan A' };
  });
  const ok = await loadCurrentScenario(() => { throw new Error('assembled inputs failed'); });
  assertEqual([ok, currentScenarioName], [false, null]);
  assertTrue(/Could not load "Plan A": assembled inputs failed/.test(status().textContent), status().textContent);
});

test('loadCurrentScenario: failing to read the current name is reported', async () => {
  barSetup((s) => s.failOn('GET', '/api/scenarios/current', 500));
  const ok = await loadCurrentScenario(() => {});
  assertEqual(ok, false);
  assertTrue(/Could not check for a current scenario/.test(status().textContent), status().textContent);
});

test('loadCurrentScenario: a network failure says the server is unreachable', async () => {
  barSetup((s) => s.failOn('GET', '/api/scenarios/current', 0));
  await loadCurrentScenario(() => {});
  assertTrue(/Could not reach the server/.test(status().textContent), status().textContent);
});

// ── Save ──────────────────────────────────────────────────────────────────

test('saveCurrentScenario: saves, merging with the stored scenario, and reports success', async () => {
  const { server } = barSetup((s) => { s.scenarios['Plan A'] = { name: 'Plan A', keep: 'other-page' }; });
  currentScenarioName = 'Plan A';
  await saveCurrentScenario(gatherStub);
  assertEqual(server.scenarios['Plan A'].keep, 'other-page');
  assertEqual(server.scenarios['Plan A'].inputs.tax_year, 2031);
  assertTrue(status().className.indexOf('ok') !== -1 && /Saved "Plan A"/.test(status().textContent));
});

test('saveCurrentScenario: a failed save is reported as an error', async () => {
  barSetup((s) => {
    s.scenarios['Plan A'] = { name: 'Plan A' };
    s.failOn('POST', '/api/scenarios/Plan', 500);
  });
  currentScenarioName = 'Plan A';
  await saveCurrentScenario(gatherStub);
  assertTrue(/Could not save "Plan A": disk full/.test(status().textContent), status().textContent);
  assertTrue(status().className.indexOf('error') !== -1);
});

test('saveCurrentScenario: a failed lookup of the stored scenario does not overwrite it', async () => {
  const { server } = barSetup((s) => {
    s.scenarios['Plan A'] = { name: 'Plan A', keep: 'x' };
    s.failOn('GET', '/api/scenarios/Plan', 500);
  });
  currentScenarioName = 'Plan A';
  await saveCurrentScenario(gatherStub);
  assertEqual(server.callsMatching('POST', '/api/scenarios/Plan A').length, 0);
  assertEqual(server.scenarios['Plan A'].keep, 'x');
  assertTrue(status().className.indexOf('error') !== -1);
});

test('saveCurrentScenario: a scenario file that vanished (404) is saved as new', async () => {
  const { server } = barSetup();
  currentScenarioName = 'Plan A';
  await saveCurrentScenario(gatherStub);
  assertTrue('Plan A' in server.scenarios);
});

test('saveCurrentScenario: network failure reports the server is unreachable', async () => {
  barSetup((s) => {
    s.scenarios['Plan A'] = { name: 'Plan A' };
    s.failOn('POST', '/api/scenarios/Plan', 0);
  });
  currentScenarioName = 'Plan A';
  await saveCurrentScenario(gatherStub);
  assertTrue(/Could not reach the server/.test(status().textContent), status().textContent);
});

test('saveCurrentScenario: does nothing when no scenario is loaded', async () => {
  const { server } = barSetup();
  await saveCurrentScenario(gatherStub);
  assertEqual(server.calls.length, 0);
});

test('saveAsScenario: a cancelled prompt does nothing', async () => {
  const { server } = barSetup();
  globalThis.prompt = () => null;
  await saveAsScenario(gatherStub);
  assertEqual(server.calls.length, 0);
});

test('saveAsScenario: saves under the trimmed name, makes it current, and updates the bar', async () => {
  const { server } = barSetup();
  globalThis.prompt = () => '  New Plan  ';
  await saveAsScenario(gatherStub);
  assertTrue('New Plan' in server.scenarios);
  assertEqual([server.current, currentScenarioName], ['New Plan', 'New Plan']);
  assertEqual(el('scenario-name-display').textContent, '📋 New Plan');
  assertTrue(status().className.indexOf('ok') !== -1);
});

test('saveAsScenario: an existing name asks before overwriting, and keeps it on decline', async () => {
  const { server } = barSetup((s) => { s.scenarios['Plan A'] = { name: 'Plan A', keep: 'y' }; });
  globalThis.prompt = () => 'Plan A';
  globalThis.confirm = () => false;
  await saveAsScenario(gatherStub);
  assertEqual(server.callsMatching('POST', '/api/scenarios/Plan A').length, 0);
  assertEqual(server.scenarios['Plan A'].keep, 'y');
});

test('saveAsScenario: accepting the overwrite saves, merged with the stored scenario', async () => {
  const { server } = barSetup((s) => { s.scenarios['Plan A'] = { name: 'Plan A', keep: 'y' }; });
  globalThis.prompt = () => 'Plan A';
  globalThis.confirm = () => true;
  await saveAsScenario(gatherStub);
  assertEqual([server.scenarios['Plan A'].keep, currentScenarioName], ['y', 'Plan A']);
});

test('saveAsScenario: a failed save is reported and does not switch scenarios', async () => {
  const { server } = barSetup((s) => s.failOn('POST', '/api/scenarios/Plan', 500));
  globalThis.prompt = () => 'Plan B';
  await saveAsScenario(gatherStub);
  assertTrue(/Could not save "Plan B": disk full/.test(status().textContent), status().textContent);
  assertEqual([currentScenarioName, server.current], [null, null]);
});

test('saveAsScenario: saved but could not become current is reported as such', async () => {
  const { server } = barSetup((s) => s.failOn('POST', '/api/scenarios/current', 500));
  globalThis.prompt = () => 'Plan C';
  await saveAsScenario(gatherStub);
  assertTrue('Plan C' in server.scenarios);
  assertTrue(/Saved "Plan C", but could not make it the current/.test(status().textContent), status().textContent);
  assertTrue(status().className.indexOf('error') !== -1);
  assertEqual(currentScenarioName, null);
});

test('saveAsScenario: a failed existence check does not save', async () => {
  const { server } = barSetup((s) => s.failOn('GET', '/api/scenarios/Plan', 500));
  globalThis.prompt = () => 'Plan D';
  await saveAsScenario(gatherStub);
  assertEqual(server.callsMatching('POST', '/api/scenarios/Plan D').length, 0);
  assertTrue(/Could not save/.test(status().textContent), status().textContent);
});

// ── Wiring ────────────────────────────────────────────────────────────────

test('wireScenarioButtons connects Save and Save As when the page has them', async () => {
  const { server } = barSetup();
  document.getElementById('save-btn');
  document.getElementById('save-as-btn');
  wireScenarioButtons(gatherStub);
  globalThis.prompt = () => 'Wired';
  await el('save-as-btn').click();
  await settle();
  assertTrue('Wired' in server.scenarios);
});

test('wireScenarioButtons tolerates pages without Save buttons', () => {
  barSetup(null, { absent: ['save-btn', 'save-as-btn'] });
  wireScenarioButtons(gatherStub); // must not throw
  currentScenarioName = 'Plan A';
  updateScenarioBar(); // must not throw either
  assertEqual(el('scenario-name-display').textContent, '📋 Plan A');
});
