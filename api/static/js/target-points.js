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
  aca: 'ACA subsidy loss',
  irmaa: 'IRMAA',
};

const TARGET_GREEN = '#16a34a';
const TARGET_DARK = '#212529';
const TARGET_OVER = '#dc2626';

// The max EMR box holds a percent; the API takes a rate. Null when blank or invalid.
function parseMaxEmrPercent(text) {
  const percent = parseFloat(text);
  return Number.isFinite(percent) && percent >= 0 ? percent / 100 : null;
}

// A rate as the text for the max EMR box.
function percentInputValue(rate) {
  return String(Number((rate * 100).toFixed(2)));
}

// People who will be on Medicare when this income is looked at: the taxpayer and, when the
// spouse's box is shown, the spouse. IRMAA counts only when this is above zero.
function irmaaEnrollees(taxpayerTicked, spouseTicked, spouseShown) {
  return (taxpayerTicked ? 1 : 0) + (spouseShown && spouseTicked ? 1 : 0);
}

// The IRMAA threshold growth to send: the typed percent when adjusting for inflation,
// otherwise zero (the published thresholds). Null when adjusting with an invalid rate.
function irmaaInflationRate(adjust, percentText) {
  return adjust ? parseMaxEmrPercent(percentText) : 0;
}

// The Calculate request plus the target settings.
function targetPointsPayload(calculatePayload, { maxEmr, includeIrmaa, enrollees, inflationRate }) {
  return {
    ...calculatePayload,
    max_emr: maxEmr,
    include_irmaa: includeIrmaa,
    irmaa_enrollees: enrollees,
    irmaa_inflation_rate: inflationRate,
  };
}

// A reminder when IRMAA tiers start above the sweep, so their cliffs cannot be targets.
// Empty when IRMAA is left out or every tier is inside the sweep.
function irmaaRangeHint(thresholds, sweepMaxMagi, includeIrmaa) {
  if (!includeIrmaa || sweepMaxMagi == null) return '';
  const above = thresholds.filter((t) => t > sweepMaxMagi).length;
  if (above === 0) return '';
  return above === 1
    ? '1 IRMAA tier starts above this sweep, so no target is found for it. '
      + 'Raise the sweep ceiling to include it.'
    : `${above} IRMAA tiers start above this sweep, so no targets are found for them. `
      + 'Raise the sweep ceiling to include them.';
}

function targetCauseText(causes) {
  if (!causes.length) return '—';
  return causes.map((cause) => TARGET_CAUSE_LABELS[cause] ?? cause).join(', ');
}

// One table row per desirable leg, as display strings.
// ``label`` (for the legs over the max) is shown in front of what each leg includes.
function targetLegRows(legs, label = '') {
  return legs.map((leg) => ({
    from: fmt$(leg.from_income),
    to: fmt$(leg.to_income),
    average: formatRatePercent(leg.average_emr),
    cost: fmt$(leg.cost),
    causes: label ? `${label}: ${targetCauseText(leg.causes)}` : targetCauseText(leg.causes),
    over: label !== '',
  }));
}

// The table rows for a response, in income order. With ``showExtra`` the legs over the max
// (red) and the legs only reached by paying an over-max span are listed too.
function targetTableRows(result, showExtra = false) {
  const entries = result.legs.map((leg) => ({ leg, label: '' }));
  if (showExtra) {
    entries.push(...(result.over_max_legs ?? []).map((leg) => ({ leg, label: 'Over max' })));
    entries.push(...(result.unreachable_legs ?? []).map((leg) => ({ leg, label: 'Past an over-max span', ok: true })));
  }
  entries.sort((a, b) => a.leg.from_income - b.leg.from_income || a.leg.to_income - b.leg.to_income);
  return entries.map(({ leg, label, ok }) => {
    const row = targetLegRows([leg], label)[0];
    return { ...row, over: label === 'Over max', ok: ok === true };
  });
}

// Chart pieces for a response: dots on the max EMR line at each target, the dashed max
// EMR line, and a green line per desirable leg at its average rate, labelled.
function targetChartMarkers(result, showOver = false) {
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
  const over = showOver ? result.over_max_legs ?? [] : [];
  const overLines = over.map((leg) => ({
    type: 'line', x0: leg.from_income, x1: leg.to_income,
    y0: leg.average_emr, y1: leg.average_emr,
    line: { color: TARGET_OVER, width: 3, dash: 'dot' },
  }));
  const beyond = showOver ? result.unreachable_legs ?? [] : [];
  const beyondLines = beyond.map((leg) => ({
    type: 'line', x0: leg.from_income, x1: leg.to_income,
    y0: leg.average_emr, y1: leg.average_emr,
    line: { color: TARGET_GREEN, width: 3, dash: 'dot' },
  }));
  const labels = [...result.legs, ...over, ...beyond].map((leg) => ({
    x: (leg.from_income + leg.to_income) / 2, y: leg.average_emr, yshift: 12,
    text: formatRatePercent(leg.average_emr), showarrow: false,
    font: { size: 11, color: leg.average_emr > maxEmr ? TARGET_OVER : TARGET_GREEN },
  }));
  return { traces: [dots], shapes: [maxLine, ...legLines, ...overLines, ...beyondLines], annotations: labels };
}
