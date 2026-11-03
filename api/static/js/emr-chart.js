'use strict';

// The effective-marginal-rate chart pieces shared by the Income and EMR pages: the
// component list, the stacked-area and line trace builders, the base layout, drawing,
// and the Stacked/Lines toggle. Each page adds what is specific to it (Income draws
// IRMAA and ACA markers into the layout; EMR draws IRMAA after the plot).
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

// The ACA-inclusive total as a dotted line (its spike is kept out of the stack). Only
// Income's response carries total_cost_emr; null when it is absent or all zero.
function totalCostTrace(pts) {
  if (!pts.total_cost_emr || allZero(pts.total_cost_emr)) return null;
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
