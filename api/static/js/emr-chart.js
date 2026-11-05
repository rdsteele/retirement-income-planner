'use strict';

// The effective-marginal-rate chart pieces shared by the Income and EMR pages: the
// component list, the stacked-area and line trace builders, the base layout, drawing,
// and the Stacked/Lines toggle. Each page adds what is specific to it (Income draws
// IRMAA markers into the layout; EMR draws them after the plot).
// Depends on common.js. Declarations only: nothing runs at load time.

// Component metadata: response key, legend label, color.
const EMR_COMPONENTS = [
  { key: 'ordinary', label: 'Ordinary', color: '#4a86c8' },
  { key: 'ss_torpedo', label: 'SS Torpedo', color: '#f59e0b' },
  { key: 'pref_stacking', label: 'Pref Stacking', color: '#8b5cf6' },
  { key: 'niit', label: 'NIIT', color: '#ef4444' },
  { key: 'ohio', label: 'Ohio', color: '#0d9488' },
];

// 'stacked' or 'lines'.
let chartMode = 'stacked';

// Components that have any non-zero value, in display order.
function visibleComponents(pts) {
  return EMR_COMPONENTS.filter((comp) => !allZero(pts.components[comp.key]));
}

// The ACA-inclusive total as a dotted line (its spike is kept out of the stack). Null
// unless the subsidy loss adds something: with ACA off it would only repeat the total.
function totalCostTrace(pts) {
  if (!pts.total_cost_emr || !pts.emr_aca || allZero(pts.emr_aca)) return null;
  return {
    type: 'scatter',
    x: pts.income,
    y: pts.total_cost_emr,
    name: 'Total Cost EMR (incl. ACA)',
    mode: 'lines',
    line: { color: '#dc2626', width: 2, dash: 'dot' },
    hovertemplate: 'Total Cost EMR: %{y:.1%}<extra></extra>',
  };
}

function buildStackedTraces(pts) {
  const traces = visibleComponents(pts).map((comp, index) => ({
    type: 'scatter',
    x: pts.income,
    y: pts.components[comp.key],
    name: comp.label,
    fill: index === 0 ? 'tozeroy' : 'tonexty',
    stackgroup: 'emr',
    line: { color: comp.color, width: 0 },
    fillcolor: comp.color,
    hovertemplate: comp.label + ': %{y:.1%}<extra></extra>',
  }));
  const totalCost = totalCostTrace(pts);
  return totalCost ? [...traces, totalCost] : traces;
}

function buildLineTraces(pts) {
  const traces = visibleComponents(pts).map((comp) => ({
    type: 'scatter',
    x: pts.income,
    y: pts.components[comp.key],
    name: comp.label,
    mode: 'lines',
    line: { color: comp.color, width: 2 },
    hovertemplate: comp.label + ': %{y:.1%}<extra></extra>',
  }));
  traces.push({
    type: 'scatter',
    x: pts.income,
    y: pts.emr,
    name: 'Total EMR',
    mode: 'lines',
    line: { color: '#212529', width: 3 },
    hovertemplate: 'Total EMR: %{y:.1%}<extra></extra>',
  });
  const totalCost = totalCostTrace(pts);
  return totalCost ? [...traces, totalCost] : traces;
}

// Layout common to both pages; the page adds `shapes` and `annotations`.
function buildBaseLayout(xTitle, yMax) {
  const chartEl = el('chart');
  return {
    width: chartEl.parentElement.offsetWidth || 800,
    height: 500,
    xaxis: { title: { text: xTitle }, tickformat: ',.0f' },
    yaxis: {
      title: { text: 'Effective Marginal Rate' },
      tickformat: '.1%',
      range: [0, yMax],
      autorange: false,
    },
    legend: { orientation: 'h', y: -0.25 },
    margin: { t: 20, b: 80, l: 60, r: 20 },
    hovermode: 'x unified',
  };
}

// The ACA cliff as a dotted red line with a label, from the response's planning signals.
// Empty when ACA is off or the cliff is outside the sweep.
function acaCliffMarkers(signals) {
  const cliff = signals?.aca_cliff_sweep_value;
  if (cliff === null || cliff === undefined) return { shapes: [], annotations: [] };
  return {
    shapes: [{
      type: 'line', x0: cliff, x1: cliff, y0: 0, y1: 1, yref: 'paper',
      line: { color: '#dc2626', dash: 'dot', width: 2 },
    }],
    annotations: [{
      x: cliff, y: 0.97, yref: 'paper',
      text: 'ACA Cliff ' + fmt$(cliff),
      showarrow: false,
      font: { size: 11, color: '#dc2626', weight: 'bold' },
      xanchor: 'left', yanchor: 'top',
    }],
  };
}

// Plots the points in the current mode (stacked area or lines) with the given layout.
async function drawChart(pts, layout) {
  const traces = chartMode === 'stacked' ? buildStackedTraces(pts) : buildLineTraces(pts);
  await Plotly.newPlot('chart', traces, layout, { responsive: true });
}

// Connects the Stacked Area / Lines buttons; `redraw` re-renders the page's chart.
function wireChartModeButtons(redraw) {
  const select = (mode, activeId, inactiveId) => () => {
    chartMode = mode;
    el(activeId).classList.add('active');
    el(inactiveId).classList.remove('active');
    redraw();
  };
  el('btn-stacked').addEventListener('click', select('stacked', 'btn-stacked', 'btn-lines'));
  el('btn-lines').addEventListener('click', select('lines', 'btn-lines', 'btn-stacked'));
}

// ── IRMAA threshold lines ────────────────────────────────────────────────
// The x-axis is income ADDED to the fixed income, but an IRMAA threshold is a total
// MAGI. So a threshold is drawn where the sweep point's IRMAA MAGI reaches it.

// Sweep x at which `irmaaMagi` first reaches `threshold`, or null when it never does
// within the sweep. Interpolates inside a step.
function irmaaSweepPosition(threshold, income, irmaaMagi) {
  if (!income.length || threshold < irmaaMagi[0] || threshold > irmaaMagi[irmaaMagi.length - 1]) {
    return null;
  }
  const i = irmaaMagi.findIndex((m) => m >= threshold);
  if (i === 0 || irmaaMagi[i] === threshold) return income[i];
  const share = (threshold - irmaaMagi[i - 1]) / (irmaaMagi[i] - irmaaMagi[i - 1]);
  return income[i - 1] + share * (income[i] - income[i - 1]);
}

// The IRMAA lines to draw: [{ tier, x }] for each threshold inside the sweep. `tier` is
// the threshold's 1-based number, so a label stays "IRMAA 2" when tier 1 is out of range.
function irmaaLines(thresholds, pts) {
  return thresholds
    .map((t, i) => ({ tier: i + 1, x: irmaaSweepPosition(t, pts.income, pts.irmaa_magi) }))
    .filter((line) => line.x !== null);
}
