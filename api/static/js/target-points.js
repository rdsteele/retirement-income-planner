'use strict';

// Target income points: the request the Income page sends, the table rows, and the
// chart markers for the response of POST /api/target-points. Depends on common.js.
// Declarations only: nothing runs at load time.

// What drives a costly stretch, by the identifiers the API uses.
const TARGET_CAUSE_LABELS = {
  bracket: 'Higher bracket',
  ss_torpedo: 'SS torpedo',
  pref_stacking: 'LTCG stacking',
  niit: 'NIIT',
  aca: 'ACA cliff',
  irmaa: 'IRMAA',
};

const TARGET_GREEN = '#16a34a';
const TARGET_DARK = '#212529';

// The max EMR box holds a percent; the API takes a rate. Null when blank or invalid.
function parseMaxEmrPercent(text) {
  const percent = parseFloat(text);
  return Number.isFinite(percent) && percent >= 0 ? percent / 100 : null;
}

// A rate as the text for the max EMR box.
function percentInputValue(rate) {
  return String(Number((rate * 100).toFixed(2)));
}

// Blank means everyone on the return pays (the server's default), so it is sent as null.
function parseEnrollees(text) {
  const count = parseInt(text, 10);
  return Number.isInteger(count) && count >= 0 ? count : null;
}

// The Calculate request plus the target settings.
function targetPointsPayload(calculatePayload, { maxEmr, includeIrmaa, enrollees }) {
  return {
    ...calculatePayload,
    max_emr: maxEmr,
    include_irmaa: includeIrmaa,
    irmaa_enrollees: enrollees,
  };
}

function targetCauseText(causes) {
  if (!causes.length) return '—';
  return causes.map((cause) => TARGET_CAUSE_LABELS[cause] ?? cause).join(', ');
}

// One table row per desirable leg, as display strings.
function targetLegRows(legs) {
  return legs.map((leg) => ({
    from: fmt$(leg.from_income),
    to: fmt$(leg.to_income),
    average: formatRatePercent(leg.average_emr),
    cost: fmt$(leg.cost),
    causes: targetCauseText(leg.causes),
  }));
}

// Chart pieces for a response: dots on the max EMR line at each target, the dashed max
// EMR line, and a green line per desirable leg at its average rate, labelled.
function targetChartMarkers(result) {
  const maxEmr = result.max_emr;
  const dots = {
    type: 'scatter',
    mode: 'markers',
    x: result.targets,
    y: result.targets.map(() => maxEmr),
    name: 'Target points',
    marker: { color: TARGET_DARK, size: 9, symbol: 'circle-open', line: { width: 2 } },
    hovertemplate: 'Target: $%{x:,.0f}<extra></extra>',
  };
  const maxLine = {
    type: 'line', xref: 'paper', x0: 0, x1: 1, y0: maxEmr, y1: maxEmr,
    line: { color: TARGET_DARK, dash: 'dash', width: 1 },
  };
  const legLines = result.legs.map((leg) => ({
    type: 'line', x0: leg.from_income, x1: leg.to_income,
    y0: leg.average_emr, y1: leg.average_emr,
    line: { color: TARGET_GREEN, width: 4 },
  }));
  const labels = result.legs.map((leg) => ({
    x: (leg.from_income + leg.to_income) / 2, y: leg.average_emr, yshift: 12,
    text: formatRatePercent(leg.average_emr), showarrow: false,
    font: { size: 11, color: TARGET_GREEN },
  }));
  return { traces: [dots], shapes: [maxLine, ...legLines], annotations: labels };
}
