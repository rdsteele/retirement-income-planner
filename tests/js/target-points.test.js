// Tests for api/static/js/target-points.js and the Income page's Target Points card.

const SAMPLE_TARGETS = {
  max_emr: 0.25,
  targets: [0, 56000, 130000],
  legs: [
    { from_income: 0, to_income: 56000, average_emr: 0.142, cost: 7952, causes: [] },
    { from_income: 56000, to_income: 130000, average_emr: 0.2331, cost: 17249, causes: ['ss_torpedo', 'irmaa'] },
  ],
};

// ── Shared helpers ────────────────────────────────────────────────────────

test('the max EMR box takes a percent and sends a rate', () => {
  assertEqual(parseMaxEmrPercent('25'), 0.25);
  assertEqual(parseMaxEmrPercent('0'), 0);
  assertEqual(parseMaxEmrPercent('12.5'), 0.125);
});

test('a blank, non-numeric, or negative max EMR is not a rate', () => {
  assertEqual(parseMaxEmrPercent(''), null);
  assertEqual(parseMaxEmrPercent('abc'), null);
  assertEqual(parseMaxEmrPercent('-1'), null);
});

test('a rate is shown in the box as a clean percent', () => {
  assertEqual(percentInputValue(0.25), '25');
  assertEqual(percentInputValue(0.125), '12.5');
  assertEqual(percentInputValue(0.07), '7');
});

test('a blank enrollee box means everyone, so it is sent as null', () => {
  assertEqual(parseEnrollees(''), null);
  assertEqual(parseEnrollees('0'), 0);
  assertEqual(parseEnrollees('2'), 2);
  assertEqual(parseEnrollees('-1'), null);
});

test('the target points request adds the settings to the Calculate request', () => {
  const body = targetPointsPayload({ filing_status: 'x', tax_year: 1 }, {
    maxEmr: 0.2, includeIrmaa: true, enrollees: null, inflationRate: 0.03,
  });
  assertEqual(body, {
    filing_status: 'x', tax_year: 1, max_emr: 0.2, include_irmaa: true, irmaa_enrollees: null,
    irmaa_inflation_rate: 0.03,
  });
});

test('IRMAA growth is zero unless adjusting, a rate when adjusting, null when that is invalid', () => {
  assertEqual(irmaaInflationRate(false, '2.5'), 0);
  assertEqual(irmaaInflationRate(false, ''), 0);
  assertEqual(irmaaInflationRate(true, '2.5'), 0.025);
  assertEqual(irmaaInflationRate(true, ''), null);
  assertEqual(irmaaInflationRate(true, '-1'), null);
});

test('causes are listed with readable names and a dash when there are none', () => {
  assertEqual(targetCauseText([]), '—');
  assertEqual(targetCauseText(['ss_torpedo', 'irmaa']), 'SS torpedo, IRMAA');
  assertEqual(targetCauseText(['something_new']), 'something_new');
});

test('each desirable leg becomes a row of display strings', () => {
  assertEqual(targetLegRows(SAMPLE_TARGETS.legs), [
    { from: '$0', to: '$56,000', average: '14.2%', cost: '$7,952', causes: '—', over: false },
    { from: '$56,000', to: '$130,000', average: '23.31%', cost: '$17,249', causes: 'SS torpedo, IRMAA', over: false },
  ]);
});

test('legs over the max are labelled in the table and drawn dotted red on the chart', () => {
  const over = [{ from_income: 15000, to_income: 23000, average_emr: 0.225, cost: 1800, causes: ['aca'] }];
  const row = targetLegRows(over, 'Over max')[0];
  assertEqual([row.causes, row.over], ['Over max: ACA subsidy loss', true]);
  const result = { ...SAMPLE_TARGETS, over_max_legs: over };
  assertEqual(targetChartMarkers(result).shapes.length, 3);
  const shown = targetChartMarkers(result, true);
  assertEqual(shown.shapes[shown.shapes.length - 1].line.dash, 'dot');
  assertEqual(shown.annotations[shown.annotations.length - 1].text, '22.5%');
});

const BLOCKED = {
  max_emr: 0.32,
  targets: [0, 23000, 70000, 98000],
  legs: [{ from_income: 0, to_income: 23000, average_emr: 0.1842, cost: 4295, causes: [] }],
  over_max_legs: [{ from_income: 23000, to_income: 70000, average_emr: 0.4136, cost: 19192, causes: ['aca'] }],
  unreachable_legs: [{ from_income: 70000, to_income: 98000, average_emr: 0.2885, cost: 8078, causes: ['irmaa'] }],
};

test('the table lists only reachable legs until the extra segments are asked for', () => {
  assertEqual(targetTableRows(BLOCKED).map((r) => r.from), ['$0']);
});

test('the extra segments are listed in income order, labelled, and told apart', () => {
  const rows = targetTableRows(BLOCKED, true);
  assertEqual(rows.map((r) => r.from), ['$0', '$23,000', '$70,000']);
  assertEqual(rows.map((r) => r.over), [false, true, false]);
  assertEqual(rows.map((r) => r.ok), [false, false, true]);
  assertEqual(rows[2].causes, 'Past an over-max span: IRMAA');
});

test('segments past an over-max span are drawn green and dotted when asked for', () => {
  assertEqual(targetChartMarkers(BLOCKED).shapes.length, 2);
  const { shapes, annotations } = targetChartMarkers(BLOCKED, true);
  const last = shapes[shapes.length - 1];
  assertEqual([last.x0, last.x1, last.line.dash], [70000, 98000, 'dot']);
  assertEqual(last.line.color, shapes[1].line.color);
  assertEqual(annotations[annotations.length - 1].text, '28.85%');
});

test('chart markers put dots on the max EMR line and a labelled green line on each leg', () => {
  const { traces, shapes, annotations } = targetChartMarkers(SAMPLE_TARGETS);
  assertEqual(traces.length, 1);
  assertEqual(traces[0].name, 'Target points');
  assertEqual(traces[0].x, [0, 56000, 130000]);
  assertEqual(traces[0].y, [0.25, 0.25, 0.25]);
  assertEqual(shapes[0].y0, 0.25);
  assertEqual(shapes[0].xref, 'paper');
  assertEqual(shapes.slice(1).map((s) => [s.x0, s.x1, s.y0]), [[0, 56000, 0.142], [56000, 130000, 0.2331]]);
  assertEqual(annotations.map((a) => [a.x, a.text]), [[28000, '14.2%'], [93000, '23.31%']]);
});

test('chart markers with no legs still show the max EMR line and the dots', () => {
  const { shapes, annotations } = targetChartMarkers({ max_emr: 0.2, targets: [0, 9], legs: [] });
  assertEqual(shapes.length, 1);
  assertEqual(annotations, []);
});

test('drawChart adds extra traces after the page traces', async () => {
  const page = installFakePage();
  await drawChart(
    { income: [0], emr: [0.1], components: { ordinary: [0.1], ss_torpedo: [0], pref_stacking: [0], niit: [0], ohio: [0] } },
    {},
    [{ name: 'extra' }],
  );
  const traces = page.plotly.calls[0].args[1];
  assertEqual(traces[traces.length - 1].name, 'extra');
});

// ── Income page ───────────────────────────────────────────────────────────

const tick = (id, on = true) => {
  document.getElementById(id).type = 'checkbox';
  document.getElementById(id).checked = on;
};

async function calculated(configure) {
  const app = await startPage('income', (server, page) => {
    FX.config.target_emr_rate_default = 0.31;
    tick('target_include_irmaa');
    tick('target-toggle');
    if (configure) configure(server, page);
  });
  await app.el('calc-btn').click();
  await settle();
  return app;
}

test('income: the max EMR box starts at the configured default', async () => {
  const app = await startPage('income', () => { FX.config.target_emr_rate_default = 0.31; });
  assertEqual(app.el('target_max_emr').value, '31');
});

test('income: Calculate asks for target points with the same inputs plus the settings', async () => {
  const app = await calculated();
  const [calc] = app.server.callsMatching('POST', '/api/income-plan/calculate');
  const posts = app.server.callsMatching('POST', '/api/target-points');
  assertEqual(posts.length, 1);
  assertEqual(posts[0].body, {
    ...calc.body, max_emr: 0.31, include_irmaa: true, irmaa_enrollees: null,
    irmaa_inflation_rate: 0,
  });
});

test('income: the target table lists the desirable legs', async () => {
  const app = await calculated();
  const html = app.el('target-points-body').innerHTML;
  assertEqual(app.el('target-points-section').style.display, 'block');
  for (const leg of FX.target_points.legs) {
    assertTrue(html.indexOf(fmt$(leg.to_income)) !== -1, 'missing target ' + leg.to_income);
  }
});

test('income: the chart shows the target markers while the box is ticked', async () => {
  const app = await calculated();
  const plot = lastPlot(app);
  assertTrue(traceNames(plot).indexOf('Target points') !== -1, 'missing target dots');
  assertTrue(plot.layout.shapes.some((s) => s.y0 === FX.target_points.max_emr && s.xref === 'paper'), 'missing max EMR line');
});

test('income: unticking Target Points removes the markers', async () => {
  const app = await calculated();
  app.el('target-toggle').checked = false;
  await app.el('target-toggle').dispatch('change');
  await settle();
  assertEqual(traceNames(lastPlot(app)).indexOf('Target points'), -1);
  assertTrue(!lastPlot(app).layout.shapes.some((s) => s.y0 === FX.target_points.max_emr), 'max EMR line remains');
});

test('income: changing the max EMR asks again using the last Calculate inputs', async () => {
  const app = await calculated();
  app.el('pension').value = '99999'; // changed after Calculate: must not be sent
  app.el('target_max_emr').value = '20';
  await app.el('target_max_emr').dispatch('change');
  await settle();
  const posts = app.server.callsMatching('POST', '/api/target-points');
  assertEqual(posts.length, 2);
  assertEqual(posts[1].body.max_emr, 0.2);
  assertEqual(posts[1].body.pension, posts[0].body.pension);
});

test('income: Medicare enrollees and Include IRMAA are sent', async () => {
  const app = await calculated();
  app.el('target_irmaa_enrollees').value = '1';
  tick('target_include_irmaa', false);
  await app.el('target_irmaa_enrollees').dispatch('change');
  await settle();
  const last = app.server.callsMatching('POST', '/api/target-points').pop();
  assertEqual([last.body.irmaa_enrollees, last.body.include_irmaa], [1, false]);
});

test('income: an invalid max EMR is explained and nothing is requested', async () => {
  const app = await calculated();
  app.el('target_max_emr').value = '';
  await app.el('target_max_emr').dispatch('change');
  await settle();
  assertEqual(app.server.callsMatching('POST', '/api/target-points').length, 1);
  assertTrue(app.el('target-points-note').children[0].textContent.indexOf('max EMR') !== -1, 'no explanation shown');
  assertEqual(app.el('target-points-body').innerHTML, '');
});

test('income: a target points failure is shown beside the table and the chart still draws', async () => {
  const app = await calculated((server) => server.failOn('POST', '/api/target-points', 500));
  assertTrue(app.el('target-points-note').children[0].textContent.indexOf('Target points unavailable') !== -1, 'no failure note');
  assertEqual(errorShown(app), null);
  assertTrue(app.page.plotly.calls.some((c) => c.name === 'newPlot'), 'chart was not drawn');
  assertEqual(traceNames(lastPlot(app)).indexOf('Target points'), -1);
});

test('income: a response with no desirable leg says so', async () => {
  const app = await calculated(() => { FX.target_points.legs = []; });
  assertTrue(app.el('target-points-note').children[0].textContent.indexOf('No leg') !== -1, 'no empty note');
});

// ── IRMAA thresholds: lines and targets agree ─────────────────────────────

test('income: the growth rate box starts at the configured rate', async () => {
  const app = await startPage('income', () => { FX.config.irmaa_inflation_default = 0.035; });
  assertEqual(app.el('target_irmaa_inflation_rate').value, '3.5');
});

test('income: IRMAA growth is not sent unless the box is ticked', async () => {
  const app = await calculated();
  assertEqual(app.server.callsMatching('POST', '/api/target-points')[0].body.irmaa_inflation_rate, 0);
});

test('income: ticking Adjust IRMAA for Inflation sends the typed rate and shows the box', async () => {
  const app = await calculated();
  tick('target_irmaa_inflation_adj');
  app.el('target_irmaa_inflation_rate').value = '4';
  await app.el('target_irmaa_inflation_adj').dispatch('change');
  await settle();
  const last = app.server.callsMatching('POST', '/api/target-points').pop();
  assertEqual(last.body.irmaa_inflation_rate, 0.04);
  assertEqual(app.el('target-inflation-rate-wrap').classList.contains('hidden'), false);
});

test('income: an invalid growth rate is explained and nothing is requested', async () => {
  const app = await calculated();
  tick('target_irmaa_inflation_adj');
  app.el('target_irmaa_inflation_rate').value = '';
  await app.el('target_irmaa_inflation_adj').dispatch('change');
  await settle();
  assertEqual(app.server.callsMatching('POST', '/api/target-points').length, 1);
  assertTrue(app.el('target-points-note').children[0].textContent.indexOf('growth rate') !== -1, 'no explanation shown');
});

// IRMAA lines come from the thresholds the target points were placed with.
async function calculatedWithIrmaaLines(inflation) {
  const app = await startPage('income', () => {
    tick('irmaa-toggle');
    tick('target_include_irmaa');
    tick('target_irmaa_inflation_adj', inflation > 0);
    FX.config.irmaa_lookback_years = 2;
    const r = FX.income_plan_calculate;
    r.irmaa_thresholds = [50000]; // published
    r.points.irmaa_magi = r.points.income.map((x) => x + 40000);
    r.planning_signals.aca_cliff_sweep_value = null;
    FX.target_points.irmaa_thresholds = [55000]; // as the server placed the targets
  });
  app.el('target_irmaa_inflation_rate').value = String(inflation * 100);
  await app.el('calc-btn').click();
  await settle();
  return app;
}

test('income: the IRMAA lines use the thresholds the targets were placed with', async () => {
  const app = await calculatedWithIrmaaLines(0);
  const { shapes, annotations } = lastPlot(app).layout;
  assertEqual(shapes.filter((s) => s.yref === 'paper' && s.xref !== 'paper').map((s) => s.x0), [15000]);
  assertEqual(annotations.map((a) => a.text).filter((t) => t.indexOf('IRMAA') === 0), ['IRMAA 1']);
});

test('income: a grown threshold is labelled with the year it applies to', async () => {
  const app = await calculatedWithIrmaaLines(0.03);
  const labels = lastPlot(app).layout.annotations.map((a) => a.text);
  assertTrue(labels.indexOf('IRMAA 1 (est. ' + (DEFAULT_YEAR() + 2) + ')') !== -1, 'missing estimate label: ' + labels);
});

test('income: with IRMAA left out of the targets the lines keep the published thresholds', async () => {
  const app = await startPage('income', () => {
    tick('irmaa-toggle');
    const r = FX.income_plan_calculate;
    r.irmaa_thresholds = [50000];
    r.points.irmaa_magi = r.points.income.map((x) => x + 40000);
    r.planning_signals.aca_cliff_sweep_value = null;
    FX.target_points.irmaa_thresholds = [];
  });
  await app.el('calc-btn').click();
  await settle();
  const { shapes } = lastPlot(app).layout;
  assertEqual(shapes.filter((s) => s.yref === 'paper' && s.xref !== 'paper').map((s) => s.x0), [10000]);
});

// ── The shared panel ──────────────────────────────────────────────────────

async function panelOnAnotherEndpoint(configure) {
  const app = await startPage('income', configure);
  app.server.handle('POST', '/api/other-target-points', () => ({ status: 200, body: FX.target_points }));
  const changes = [];
  const panel = createTargetPanel({ endpoint: '/api/other-target-points', onChange: () => changes.push(1) });
  return { app, panel, changes };
}

test('panel: it posts the page request and settings to the endpoint it was given', async () => {
  const { app, panel } = await panelOnAnotherEndpoint(() => { FX.config.target_emr_rate_default = 0.28; });
  await panel.load({ filing_status: 'x', tax_year: 1 });
  const [call] = app.server.callsMatching('POST', '/api/other-target-points');
  assertEqual(call.body.filing_status, 'x');
  assertEqual(call.body.max_emr, 0.28);
});

test('panel: nothing is drawn and the published thresholds stand until targets load', async () => {
  const { panel } = await panelOnAnotherEndpoint();
  assertEqual(panel.overlay(), { traces: [], shapes: [], annotations: [] });
  assertEqual(panel.irmaaThresholds([1, 2]), [1, 2]);
  assertEqual(panel.irmaaSuffix(2030, 2), '');
});

test('panel: after loading it supplies the markers and the thresholds the server used', async () => {
  const { panel } = await panelOnAnotherEndpoint(() => {
    tick('target-toggle');
    FX.target_points.irmaa_thresholds = [77000];
  });
  await panel.load({});
  assertEqual(panel.irmaaThresholds([1]), [77000]);
  assertEqual(panel.overlay().traces.length, 1);
});

test('panel: a change redraws only once there is a request to repeat', async () => {
  const { app, panel, changes } = await panelOnAnotherEndpoint();
  panel.wire();
  await app.el('target_max_emr').dispatch('change');
  await settle();
  assertEqual(changes.length, 0);
  await panel.load({});
  await app.el('target_max_emr').dispatch('change');
  await settle();
  assertEqual(changes.length, 1);
});

// ── EMR page ──────────────────────────────────────────────────────────────

const sweepPosts = (app) => app.server.calls.filter(
  (c) => c.method === 'POST' && c.url === '/api/total-cost/target-points');

async function emrRun(configure) {
  return startPage('emr', (server, page) => {
    FX.config.target_emr_rate_default = 0.31;
    tick('target_include_irmaa');
    tick('target-toggle');
    if (configure) configure(server, page);
  });
}

test('emr: the max EMR box starts at the configured default', async () => {
  const app = await emrRun();
  assertEqual(app.el('target_max_emr').value, '31');
});

test('emr: the run asks for target points with the same request plus the settings', async () => {
  const app = await emrRun();
  const [run] = app.server.calls.filter((c) => c.method === 'POST' && c.url === '/api/total-cost');
  const posts = sweepPosts(app);
  assertEqual(posts.length, 1);
  assertEqual(posts[0].body, {
    ...run.body, max_emr: 0.31, include_irmaa: true, irmaa_enrollees: null,
    irmaa_inflation_rate: 0,
  });
});

test('emr: the target table lists the desirable legs and is shown', async () => {
  const app = await emrRun();
  assertEqual(app.el('target-points-section').style.display, 'block');
  const html = app.el('target-points-body').innerHTML;
  for (const leg of FX.target_points_sweep.legs) {
    assertTrue(html.indexOf(fmt$(leg.to_income)) !== -1, 'missing target ' + leg.to_income);
  }
});

test('emr: the chart shows the target markers while the box is ticked', async () => {
  const app = await emrRun();
  const plot = lastPlot(app);
  assertTrue(traceNames(plot).indexOf('Target points') !== -1, 'missing target dots');
  assertTrue(plot.layout.shapes.some((s) => s.y0 === FX.target_points_sweep.max_emr && s.xref === 'paper'), 'missing max EMR line');
});

test('emr: unticking Target Points removes the markers', async () => {
  const app = await emrRun();
  app.el('target-toggle').checked = false;
  await app.el('target-toggle').dispatch('change');
  await settle();
  assertEqual(traceNames(lastPlot(app)).indexOf('Target points'), -1);
});

test('emr: turning the IRMAA lines on keeps the target markers', async () => {
  const app = await emrRun(() => {
    FX.target_points_sweep.irmaa_thresholds = [50000];
    FX.total_cost.points.irmaa_magi = FX.total_cost.points.income.map((x) => x + 40000);
  });
  tick('irmaa-toggle', false);
  app.el('irmaa-toggle').checked = true;
  await app.el('irmaa-toggle').dispatch('change');
  await settle();
  const relayout = app.page.plotly.calls.filter((c) => c.name === 'relayout').pop().args[1];
  assertTrue(relayout.shapes.some((s) => s.y0 === FX.target_points_sweep.max_emr), 'target markers lost');
  assertTrue(relayout.shapes.some((s) => s.x0 === 10000), 'IRMAA line missing');
});

test('emr: the IRMAA lines use the thresholds the targets were placed with', async () => {
  const app = await emrRun(() => {
    tick('irmaa-toggle');
    FX.total_cost.irmaa_thresholds = [50000]; // published
    FX.target_points_sweep.irmaa_thresholds = [55000]; // as the server placed the targets
    FX.total_cost.points.irmaa_magi = FX.total_cost.points.income.map((x) => x + 40000);
  });
  const relayout = app.page.plotly.calls.filter((c) => c.name === 'relayout').pop().args[1];
  assertEqual(relayout.shapes.filter((s) => s.yref === 'paper' && s.xref !== 'paper').map((s) => s.x0), [15000]);
});

test('emr: changing the max EMR asks again with the last run inputs', async () => {
  const app = await emrRun();
  app.el('pension').value = '99999'; // changed after the run: must not be sent
  app.el('target_max_emr').value = '20';
  await app.el('target_max_emr').dispatch('change');
  await settle();
  const posts = sweepPosts(app);
  assertEqual(posts.length, 2);
  assertEqual(posts[1].body.max_emr, 0.2);
  assertEqual(posts[1].body.pension, posts[0].body.pension);
});

test('emr: a target points failure is shown beside the table and the chart still draws', async () => {
  const app = await emrRun((server) => server.failOn('POST', '/api/total-cost/target-points', 500));
  assertTrue(app.el('target-points-note').children[0].textContent.indexOf('Target points unavailable') !== -1, 'no failure note');
  assertEqual(errorShown(app), null);
  assertEqual(traceNames(lastPlot(app)).indexOf('Target points'), -1);
});

test('emr: tiers above the sweep are called out', async () => {
  const app = await emrRun(() => {
    FX.target_points_sweep.irmaa_thresholds = [1e9, 2e9];
  });
  assertTrue(app.el('target-range-hint').textContent.indexOf('2 IRMAA tiers') !== -1, 'no range hint');
});

test('the range hint counts tiers above the sweep and is empty otherwise', () => {
  assertEqual(irmaaRangeHint([100, 200, 300], 250, true).indexOf('1 IRMAA tier starts'), 0);
  assertEqual(irmaaRangeHint([100, 200, 300], 50, true).indexOf('3 IRMAA tiers start'), 0);
  assertEqual(irmaaRangeHint([100, 200], 250, true), '');
  assertEqual(irmaaRangeHint([100, 200, 300], 50, false), '');
  assertEqual(irmaaRangeHint([100], null, true), '');
});
