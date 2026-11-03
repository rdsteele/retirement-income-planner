// Boot tests: each real page runs against a fake DOM and the saved real API
// responses. They check that the page starts, fills its dropdowns from the API
// (not from literals), sends well-formed requests, and renders the results.
//
// The filing statuses and tax years are replaced with values no real configuration
// would contain, so a page that still falls back to a hardcoded status or year
// fails these tests.

let FX = null; // fixtures for the current test

function testFixtures() {
  const fixtures = JSON.parse(JSON.stringify(__FIXTURES));
  fixtures.config.filing_statuses = [
    { value: 'alpha', label: 'Alpha Status' },
    { value: 'beta', label: 'Beta Status' },
  ];
  fixtures.tax_years = { years: [2031, 2032], default_year: 2032 };
  fixtures.config.irmaa_lookback_years = 3;
  fixtures.config.sweep_step_default = 250;
  fixtures.config.income_plan_sweep_ceiling = 123456;
  fixtures.emr.default_sweep_ceiling = 98765;
  fixtures.emr.default_sweep_ceiling_rate = 0.31;
  fixtures.emr.planning_signals.bracket_distances = [
    { rate: 0.11, distance: 1500 },
    { rate: 0.33, distance: null },
  ];
  return fixtures;
}

const FIRST_STATUS = () => FX.config.filing_statuses[0].value;
const DEFAULT_YEAR = () => FX.tax_years.default_year;

async function startPage(name, configure) {
  FX = testFixtures();
  const page = installFakePage();
  const timers = installFakeTimers();
  const server = makeAppServer(FX);
  if (configure) configure(server, page);
  bootPage(name);
  await page.fireDocument('DOMContentLoaded');
  await settle();
  timers.runPending();
  await settle();
  return { page, timers, server, el: (id) => page.elements[id] };
}

function optionValues(select) {
  return select.children.map((o) => String(o.value));
}

function errorShown(app) {
  const box = app.el('error-msg');
  return box && box.style.display === 'block' ? box.textContent : null;
}

// ── Dropdowns come from the API on every page that has them ───────────────

for (const name of ['income', 'emr', 'tax']) {
  test(`${name}: filing status and tax year dropdowns are filled from the API`, async () => {
    const app = await startPage(name);
    assertEqual(
      optionValues(app.el('filing_status')),
      FX.config.filing_statuses.map((s) => s.value),
    );
    assertEqual(optionValues(app.el('tax_year')), FX.tax_years.years.map(String));
    assertEqual(
      app.el('filing_status').children.map((o) => o.textContent),
      FX.config.filing_statuses.map((s) => s.label),
    );
  });

  test(`${name}: a failed config request shows a page-settings error`, async () => {
    const app = await startPage(name, (server) => server.failOn('GET', '/api/config', 500));
    const message = errorShown(app);
    assertTrue(message !== null && /Could not load page settings/.test(message), String(message));
  });

  test(`${name}: a failed tax-years request shows a page-settings error`, async () => {
    const app = await startPage(name, (server) => server.failOn('GET', '/api/tax-years', 0));
    const message = errorShown(app);
    assertTrue(message !== null && /Could not load page settings/.test(message), String(message));
  });
}

// ── Tax Detail ────────────────────────────────────────────────────────────

test('tax: requests use the status and year the API offered, then render the result', async () => {
  const app = await startPage('tax');
  const posts = app.server.callsMatching('POST', '/api/tax');
  assertEqual(posts.length, 1);
  assertEqual(posts[0].body.filing_status, FIRST_STATUS());
  assertEqual(posts[0].body.tax_year, DEFAULT_YEAR());
  assertEqual(errorShown(app), null);
  assertTrue(app.el('fed-summary-list').innerHTML.indexOf('Total Federal Tax') !== -1);
  assertEqual(app.el('output-panel').style.display, '');
});

test('tax: shows the server error when the calculation fails', async () => {
  const app = await startPage('tax', (server) => server.failOn('POST', '/api/tax', 500));
  assertEqual(errorShown(app), 'disk full');
});

// ── EMR Analysis ──────────────────────────────────────────────────────────

test('emr: runs on load with API-provided status, year, and the configured sweep step', async () => {
  const app = await startPage('emr');
  const posts = app.server.callsMatching('POST', '/api/emr');
  assertEqual(posts.length, 1);
  assertEqual(posts[0].body.filing_status, FIRST_STATUS());
  assertEqual(posts[0].body.tax_year, DEFAULT_YEAR());
  assertEqual(posts[0].body.sweep_step, FX.config.sweep_step_default);
  assertEqual(errorShown(app), null);
});

test('emr: a blank sweep step is sent as null so the server applies its default', async () => {
  const app = await startPage('emr');
  app.el('sweep_step').value = '';
  app.server.calls.length = 0;
  await app.el('run-btn').click();
  await settle();
  const posts = app.server.callsMatching('POST', '/api/emr');
  assertEqual(posts.length, 1);
  assertEqual(posts[0].body.sweep_step, null);
});

test('emr: renders one badge per configured bracket rate and the default ceiling hint', async () => {
  const app = await startPage('emr');
  const badges = app.el('signals-bar').innerHTML;
  for (const d of FX.emr.planning_signals.bracket_distances) {
    const pct = formatRatePercent(d.rate);
    const expected = d.distance === null ? `At ${pct}+` : `To ${pct}: ${fmt$(d.distance)}`;
    assertTrue(badges.indexOf(expected) !== -1, `missing badge "${expected}" in ${badges}`);
  }
  const ceiling = Math.round(FX.emr.default_sweep_ceiling).toLocaleString('en-US');
  const rate = formatRatePercent(FX.emr.default_sweep_ceiling_rate);
  assertEqual(app.el('sweep_ceiling').placeholder, `${ceiling} (${rate} bracket top)`);
});

test('emr: IRMAA labels and inflation scaling use the configured lookback years', async () => {
  const app = await startPage('emr');
  const years = FX.config.irmaa_lookback_years;
  const labels = __page.buildIrmaaAnnotations([100000], true, true).map((a) => a.text);
  assertEqual(labels, [`IRMAA 1 (est. ${DEFAULT_YEAR() + years})`]);

  // 10% inflation over the lookback years, applied to a threshold inside the sweep range
  app.el('irmaa_inflation_adj').checked = true;
  app.el('irmaa_inflation_rate').value = '10';
  __page.lastResult.irmaa_thresholds = [5000];
  __page.lastResult.points.income = [0, 20000];
  const scaled = __page.effectiveIrmaaThresholds().thresholds[0];
  assertTrue(Math.abs(scaled - 5000 * 1.1 ** years) < 1e-6, `expected 5000 x 1.1^${years}, got ${scaled}`);
});

test('emr: draws the chart', async () => {
  const app = await startPage('emr');
  assertTrue(app.page.plotly.calls.some((c) => c.name === 'newPlot'), 'Plotly.newPlot was not called');
});

test('emr: shows the server error when the analysis fails', async () => {
  const app = await startPage('emr', (server) => server.failOn('POST', '/api/emr', 500));
  assertEqual(errorShown(app), 'disk full');
});

// ── Income Planning ───────────────────────────────────────────────────────

test('income: the live summary uses the API-provided status and year', async () => {
  const app = await startPage('income');
  const posts = app.server.callsMatching('POST', '/api/income-plan/summary');
  assertTrue(posts.length >= 1, 'no summary request was sent');
  assertEqual(posts[0].body.filing_status, FIRST_STATUS());
  assertEqual(posts[0].body.tax_year, DEFAULT_YEAR());
});

test('income: Calculate sends the configured ceiling, lets the server pick the step, and draws', async () => {
  const app = await startPage('income');
  await app.el('calc-btn').click();
  await settle();
  const posts = app.server.callsMatching('POST', '/api/income-plan/calculate');
  assertEqual(posts.length, 1);
  assertEqual(posts[0].body.sweep_ceiling, FX.config.income_plan_sweep_ceiling);
  assertTrue(!('sweep_step' in posts[0].body), 'sweep_step must not be hardcoded in the page');
  assertEqual(posts[0].body.filing_status, FIRST_STATUS());
  assertEqual(errorShown(app), null);
  assertTrue(app.page.plotly.calls.some((c) => c.name === 'newPlot'), 'Plotly.newPlot was not called');
});

test('income: Calculate shows the server error on failure and re-enables the button', async () => {
  const app = await startPage('income', (server) => server.failOn('POST', '/api/income-plan/calculate', 500));
  await app.el('calc-btn').click();
  await settle();
  assertEqual(errorShown(app), 'disk full');
  assertEqual(app.el('calc-btn').disabled, false);
  assertEqual(app.el('calc-btn').textContent, 'Calculate');
});

test('income: Save As stores the status and year the API offered', async () => {
  const app = await startPage('income', () => {
    globalThis.prompt = () => 'Plan A';
  });
  await app.el('save-as-btn').click();
  await settle();
  const saved = app.server.scenarios['Plan A'];
  assertTrue(!!saved, 'scenario was not saved');
  assertEqual(saved.inputs.filing_status, FIRST_STATUS());
  assertEqual(saved.inputs.tax_year, DEFAULT_YEAR());
  assertEqual(app.server.current, 'Plan A');
});

// ── Scenarios and Accounts ────────────────────────────────────────────────

test('scenarios: lists the saved scenarios', async () => {
  const app = await startPage('scenarios', (server) => {
    server.scenarios['Plan A'] = { name: 'Plan A' };
  });
  assertTrue(app.el('scenarios-list-container').innerHTML.indexOf('Plan A') !== -1);
});

test('scenarios: shows a failure to load the list', async () => {
  const app = await startPage('scenarios', (server) => server.failOn('GET', '/api/scenarios', 500));
  assertTrue(/Failed to load scenarios/.test(app.el('scenarios-list-container').innerHTML));
});

test('accounts: loads accounts on start without errors', async () => {
  const app = await startPage('accounts');
  assertTrue(app.server.callsMatching('GET', '/api/accounts').length >= 1, 'accounts were not requested');
});

// ── EMR and Tax pre-fill from a saved scenario ────────────────────────────
//
// The server folds planned and executed withdrawals into the income inputs. The
// pages must show exactly what it returns. The values below are chosen so that any
// arithmetic the page did itself on the raw scenario would give a different answer.

const SERVER_ASSEMBLED = {
  pension: 111, wages: 222, interest: 3, ordinary_dividends: 4, qualified_dividends: 5,
  ira_distributions: 777, other_investment_ordinary: 999, ss_benefit: 6, fixed_ltcg: 888,
  tax_exempt_interest: 7, above_the_line_adjustments: 8, additional_deductions: 9,
};

function savedScenario() {
  return {
    name: 'Plan A',
    inputs: { tax_year: 2031, filing_status: 'beta', ira_distributions: 1, fixed_ltcg: 2, pension_taxable: 5 },
    ohio: { include_ohio: true, gross_medical_expenses: 400 },
    aca: {},
    emr_settings: {},
    income_planning: {
      trad_withdrawals: [{ amount: 50000 }],
      withdrawals: [{ amount: 90000, basis: 10000 }],
      executed_withdrawals: [{ type: 'stcg', amount: 70000, basis: 10000 }],
    },
  };
}

function loadSavedScenario(server) {
  document.getElementById('include_ohio').type = 'checkbox'; // as in the real form
  FX.scenario_sweep_inputs = { ...SERVER_ASSEMBLED };
  server.scenarios['Plan A'] = savedScenario();
  server.current = 'Plan A';
}

for (const name of ['emr', 'tax']) {
  test(`${name}: pre-fills income from the server's assembled inputs`, async () => {
    const app = await startPage(name, loadSavedScenario);
    const value = (id) => Number(app.el(id).value);
    assertEqual(app.server.callsMatching('GET', '/api/scenarios/Plan A/sweep-inputs').length, 1);
    assertEqual(
      [value('interest'), value('ordinary_dividends'), value('qualified_dividends'), value('ira_distributions')],
      [3, 4, 5, 777],
    );
    assertEqual(
      [value('other_investment_ordinary'), value('ss_benefit'), value('fixed_ltcg'), value('tax_exempt_interest')],
      [999, 6, 888, 7],
    );
    assertEqual([value('above_the_line_adjustments'), value('additional_deductions')], [8, 9]);
    assertEqual(errorShown(app), null);
  });

  test(`${name}: takes status, year, and Ohio settings from the scenario itself`, async () => {
    const app = await startPage(name, loadSavedScenario);
    assertEqual([app.el('filing_status').value, String(app.el('tax_year').value)], ['beta', '2031']);
    assertEqual(app.el('include_ohio').checked, true);
    assertEqual(Number(app.el('gross_medical_expenses').value), 400);
  });

  test(`${name}: a failed assembled-inputs request clears the scenario and shows the error`, async () => {
    const app = await startPage(name, (server) => {
      loadSavedScenario(server);
      server.failOn('GET', '/sweep-inputs', 500);
    });
    const message = errorShown(app);
    assertTrue(message !== null && /Could not load scenario "Plan A": disk full/.test(message), String(message));
    assertEqual(app.el('scenario-name-display').textContent.indexOf('Plan A'), -1);
  });

  test(`${name}: after a failed scenario load the page does not run over the error`, async () => {
    const app = await startPage(name, (server) => {
      loadSavedScenario(server);
      server.failOn('GET', '/sweep-inputs', 500);
    });
    const endpoint = name === 'emr' ? '/api/emr' : '/api/tax';
    assertEqual(app.server.callsMatching('POST', endpoint).length, 0);
    assertTrue(errorShown(app) !== null, 'the error must still be visible');
  });
}

test('emr: pension and wages share one form field, so the field shows their sum', async () => {
  const app = await startPage('emr', loadSavedScenario);
  assertEqual(Number(app.el('pension').value), 333);
});

test('tax: pension and wages have separate fields', async () => {
  const app = await startPage('tax', loadSavedScenario);
  assertEqual([Number(app.el('pension').value), Number(app.el('wages').value)], [111, 222]);
});
