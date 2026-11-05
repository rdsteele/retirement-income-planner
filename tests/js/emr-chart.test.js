// Tests for api/static/js/emr-chart.js

// The points of a sweep response with ACA off (total_cost_emr absent).
function emrPoints() {
  return {
    income: [0, 1000, 2000],
    emr: [0.1, 0.12, 0.22],
    components: {
      ordinary: [0.1, 0.12, 0.22],
      ss_torpedo: [0, 0, 0],
      pref_stacking: [0, 0.01, 0],
      niit: [0, 0, 0],
      ohio: [0.02, 0.02, 0.02],
    },
  };
}

const names = (traces) => traces.map((t) => t.name);

test('stacked traces skip all-zero components and stack the rest in order', () => {
  const traces = buildStackedTraces(emrPoints());
  assertEqual(names(traces), ['Ordinary', 'Pref Stacking', 'Ohio']);
  assertEqual(traces.map((t) => t.fill), ['tozeroy', 'tonexty', 'tonexty']);
  assertEqual(traces.map((t) => t.stackgroup), ['emr', 'emr', 'emr']);
});

test('stacked traces use each component color and show the rate in the hover text', () => {
  const [ordinary] = buildStackedTraces(emrPoints());
  const spec = EMR_COMPONENTS.find((c) => c.key === 'ordinary');
  assertEqual(ordinary.fillcolor, spec.color);
  assertEqual(ordinary.line, { color: spec.color, width: 0 });
  assertEqual(ordinary.hovertemplate, 'Ordinary: %{y:.1%}<extra></extra>');
  assertEqual(ordinary.x, [0, 1000, 2000]);
});

test('stacked traces work when the response has no total_cost_emr (the EMR page)', () => {
  assertEqual(names(buildStackedTraces(emrPoints())).indexOf('Total Cost EMR (incl. ACA)'), -1);
});

test('stacked traces ignore an all-zero total_cost_emr', () => {
  const pts = { ...emrPoints(), total_cost_emr: [0, 0, 0], emr_aca: [0, 0, 0] };
  assertEqual(names(buildStackedTraces(pts)).indexOf('Total Cost EMR (incl. ACA)'), -1);
});

test('stacked traces skip the total-cost line when ACA adds nothing (it would only repeat the total)', () => {
  const pts = { ...emrPoints(), total_cost_emr: [0.1, 0.12, 0.22], emr_aca: [0, 0, 0] };
  assertEqual(names(buildStackedTraces(pts)).indexOf('Total Cost EMR (incl. ACA)'), -1);
});

test('stacked traces add the ACA total-cost line, dotted and unstacked, when present', () => {
  const pts = { ...emrPoints(), total_cost_emr: [0.1, 0.5, 0.22], emr_aca: [0, 0.4, 0] };
  const traces = buildStackedTraces(pts);
  const last = traces[traces.length - 1];
  assertEqual(last.name, 'Total Cost EMR (incl. ACA)');
  assertEqual(last.y, [0.1, 0.5, 0.22]);
  assertEqual(last.line.dash, 'dot');
  assertEqual(last.stackgroup, undefined);
});

test('line traces: components, then the bold Total EMR line', () => {
  const traces = buildLineTraces(emrPoints());
  assertEqual(names(traces), ['Ordinary', 'Pref Stacking', 'Ohio', 'Total EMR']);
  assertEqual(traces[0].line.width, 2);
  const total = traces[traces.length - 1];
  assertEqual([total.y, total.line.width], [[0.1, 0.12, 0.22], 3]);
});

test('line traces add the ACA total-cost line last, only when present', () => {
  assertEqual(names(buildLineTraces(emrPoints())).indexOf('Total Cost EMR (incl. ACA)'), -1);
  const traces = buildLineTraces({ ...emrPoints(), total_cost_emr: [0.1, 0.5, 0.22], emr_aca: [0, 0.4, 0] });
  assertEqual(names(traces).slice(-2), ['Total EMR', 'Total Cost EMR (incl. ACA)']);
});

test('buildBaseLayout sizes to the chart container and fixes the rate axis to the given maximum', () => {
  installFakePage();
  el('chart').parentElement.offsetWidth = 640;
  const layout = buildBaseLayout('Additional Ordinary Income ($)', 0.41);
  assertEqual(layout.width, 640);
  assertEqual(layout.height, 500);
  assertEqual(layout.xaxis.title.text, 'Additional Ordinary Income ($)');
  assertEqual(layout.yaxis.range, [0, 0.41]);
  assertEqual(layout.yaxis.autorange, false);
  assertEqual(layout.hovermode, 'x unified');
});

test('buildBaseLayout falls back to a default width when the container is not measured', () => {
  installFakePage();
  el('chart').parentElement.offsetWidth = 0;
  assertEqual(buildBaseLayout('x', 0.5).width, 800);
});

test('buildBaseLayout leaves shapes and annotations to the page', () => {
  installFakePage();
  const layout = buildBaseLayout('x', 0.5);
  assertEqual([layout.shapes, layout.annotations], [undefined, undefined]);
});

test('drawChart plots stacked traces by default and line traces in lines mode', async () => {
  const page = installFakePage();
  chartMode = 'stacked';
  await drawChart(emrPoints(), { title: 'L' });
  chartMode = 'lines';
  await drawChart(emrPoints(), { title: 'L' });
  const plots = page.plotly.calls.filter((c) => c.name === 'newPlot');
  assertEqual(plots.length, 2);
  assertEqual(plots[0].args[0], 'chart');
  assertEqual(plots[0].args[2], { title: 'L' });
  assertEqual(plots[0].args[3], { responsive: true });
  assertEqual(names(plots[0].args[1]).indexOf('Total EMR'), -1);
  assertTrue(names(plots[1].args[1]).indexOf('Total EMR') !== -1);
  chartMode = 'stacked';
});

test('wireChartModeButtons switches the mode, the active button, and redraws', async () => {
  installFakePage();
  chartMode = 'stacked';
  let redraws = 0;
  wireChartModeButtons(() => { redraws += 1; });
  await el('btn-lines').click();
  assertEqual(chartMode, 'lines');
  assertEqual([el('btn-lines').classList.contains('active'), el('btn-stacked').classList.contains('active')], [true, false]);
  await el('btn-stacked').click();
  assertEqual(chartMode, 'stacked');
  assertEqual([el('btn-stacked').classList.contains('active'), el('btn-lines').classList.contains('active')], [true, false]);
  assertEqual(redraws, 2);
});

// ── IRMAA threshold positions on the sweep axis ───────────────────────────
// irmaa_magi[i] is the IRMAA MAGI at sweep point income[i]; a threshold is drawn
// where that MAGI reaches it, not at the raw threshold value.

test('irmaa position: shifted left by the fixed income', () => {
  // fixed income 40,000: MAGI = 40,000 + sweep
  const income = [0, 10000, 20000, 30000];
  const magi = [40000, 50000, 60000, 70000];
  assertEqual(irmaaSweepPosition(55000, income, magi), 15000);
});

test('irmaa position: interpolates inside a step', () => {
  assertEqual(irmaaSweepPosition(41000, [0, 1000, 2000], [40000, 41500, 43000]), 666.6666666666666);
});

test('irmaa position: follows MAGI that rises faster than the sweep (torpedo)', () => {
  // MAGI climbs 1.85 per sweep dollar here, so the crossing comes sooner
  assertEqual(irmaaSweepPosition(1850, [0, 1000, 2000], [0, 1850, 3700]), 1000);
});

test('irmaa position: a threshold at a point lands exactly on it', () => {
  assertEqual(irmaaSweepPosition(50000, [0, 10000], [40000, 50000]), 10000);
});

test('irmaa position: null when the threshold is below the first point or above the last', () => {
  assertEqual(irmaaSweepPosition(39999, [0, 10000], [40000, 50000]), null);
  assertEqual(irmaaSweepPosition(50001, [0, 10000], [40000, 50000]), null);
});

test('irmaa position: the first point counts when MAGI starts exactly at the threshold', () => {
  assertEqual(irmaaSweepPosition(40000, [0, 10000], [40000, 50000]), 0);
});

test('irmaa position: a flat stretch reports the first point reaching the threshold', () => {
  assertEqual(irmaaSweepPosition(50000, [0, 1000, 2000, 3000], [40000, 50000, 50000, 60000]), 1000);
});

test('irmaa position: null when there are no points', () => {
  assertEqual(irmaaSweepPosition(50000, [], []), null);
});

test('irmaa lines: thresholds out of range are dropped and the rest keep their number', () => {
  const pts = { income: [0, 10000, 20000], irmaa_magi: [90000, 100000, 110000] };
  // tiers 1-3 at 85,000 / 105,000 / 150,000: tier 1 is below the sweep, tier 3 is above it
  assertEqual(irmaaLines([85000, 105000, 150000], pts), [{ tier: 2, x: 15000 }]);
});

test('irmaa lines: empty without thresholds or points', () => {
  assertEqual(irmaaLines([], { income: [0], irmaa_magi: [0] }), []);
  assertEqual(irmaaLines([100], { income: [], irmaa_magi: [] }), []);
});

test('aca cliff markers: a dotted red line and a label at the cliff', () => {
  const { shapes, annotations } = acaCliffMarkers({ aca_cliff_sweep_value: 12345 });
  assertEqual(shapes.length, 1);
  assertEqual([shapes[0].x0, shapes[0].x1, shapes[0].yref], [12345, 12345, 'paper']);
  assertEqual(shapes[0].line.dash, 'dot');
  assertEqual(annotations.map((a) => [a.x, a.text]), [[12345, 'ACA Cliff $12,345']]);
});

test('aca cliff markers: none without a cliff in the sweep', () => {
  assertEqual(acaCliffMarkers({ aca_cliff_sweep_value: null }), { shapes: [], annotations: [] });
  assertEqual(acaCliffMarkers({}), { shapes: [], annotations: [] });
  assertEqual(acaCliffMarkers(undefined), { shapes: [], annotations: [] });
});
