// Tests for api/static/js/emr-chart.js

// The points an EMR response carries (no total_cost_emr: that exists only for Income).
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
  const pts = { ...emrPoints(), total_cost_emr: [0, 0, 0] };
  assertEqual(names(buildStackedTraces(pts)).indexOf('Total Cost EMR (incl. ACA)'), -1);
});

test('stacked traces add the ACA total-cost line, dotted and unstacked, when present', () => {
  const pts = { ...emrPoints(), total_cost_emr: [0.1, 0.5, 0.22] };
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
  const traces = buildLineTraces({ ...emrPoints(), total_cost_emr: [0.1, 0.5, 0.22] });
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
