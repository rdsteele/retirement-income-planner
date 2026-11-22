'use strict';

// The Target Points card shared by the Income and EMR pages: it asks the server for the
// target points of the page's last calculation, fills the table, and supplies the chart
// markers and IRMAA threshold lines. Each page creates one panel with its own endpoint and
// redraw callback, and the card's elements use the same ids on both pages. A page that
// keeps its IRMAA growth controls elsewhere (the EMR page's chart toolbar) names them in
// `inflationControls`.
// Depends on api.js, common.js, and target-points.js. Declarations only.

// `endpoint` is the route for the page's request shape; `onChange` redraws the page's
// chart after the user changes a setting.
function createTargetPanel({ endpoint, onChange, inflationControls = {} }) {
  const adjustId = inflationControls.adjustId ?? 'target_irmaa_inflation_adj';
  const rateId = inflationControls.rateId ?? 'target_irmaa_inflation_rate';
  const wrapId = inflationControls.wrapId ?? 'target-inflation-rate-wrap';
  let request = null; // the request behind the page's current result
  let targets = null; // the server's response for that request, or null
  let grownBy = 0; // IRMAA threshold growth the targets were computed with
  let includedIrmaa = false; // whether IRMAA was part of the costs
  let sweepMax = null; // highest IRMAA MAGI the sweep reaches, when the page says

  function setNote(message) {
    const note = el('target-points-note');
    note.innerHTML = '';
    if (!message) return;
    const p = document.createElement('p');
    p.style.cssText = 'padding: 8px 14px; font-size: 12px; color: #6c757d;';
    p.textContent = message;
    note.appendChild(p);
  }

  // The settings as the request needs them, or null with the reason shown when one is
  // invalid.
  function readSettings() {
    const maxEmr = parseMaxEmrPercent(el('target_max_emr').value);
    const inflationRate = irmaaInflationRate(el(adjustId).checked, el(rateId).value);
    if (maxEmr === null) {
      setNote('Enter a max EMR of 0% or more.');
      return null;
    }
    if (inflationRate === null) {
      setNote('Enter an IRMAA growth rate of 0% or more.');
      return null;
    }
    return {
      maxEmr,
      includeIrmaa: el('target_include_irmaa').checked,
      enrollees: parseEnrollees(el('target_irmaa_enrollees').value),
      inflationRate,
    };
  }

  // A failure is shown beside the table and never hides the page's chart.
  async function fetchTargets() {
    targets = null;
    const settings = readSettings();
    if (!settings) return;
    try {
      targets = await postJson(endpoint, targetPointsPayload(request, settings));
      grownBy = settings.inflationRate;
      includedIrmaa = settings.includeIrmaa;
      setNote('');
    } catch (err) {
      setNote('Target points unavailable: ' + err.message);
    }
  }

  function renderTable() {
    const showOver = el('target_show_over').checked;
    const rows = targets ? targetTableRows(targets, showOver) : [];
    el('target-points-body').innerHTML = rows.map((r) => `<tr${r.over ? ' class="target-over"' : ''}>
        <td>${escHtml(r.from)}</td>
        <td>${escHtml(r.to)}</td>
        <td>${escHtml(r.average)}</td>
        <td>${escHtml(r.cost)}</td>
        <td>${escHtml(r.causes)}</td>
      </tr>`).join('');
    if (targets && !targets.legs.length) setNote('No leg averages at or below the max EMR.');
    renderRangeHint();
  }

  function renderRangeHint() {
    const hint = el('target-range-hint');
    if (!hint) return;
    hint.textContent = targets ? irmaaRangeHint(targets.irmaa_thresholds, sweepMax, includedIrmaa) : '';
    hint.style.display = hint.textContent ? 'block' : 'none';
  }

  async function refresh() {
    if (!request) return;
    await fetchTargets();
    renderTable();
    onChange();
  }

  return {
    // Fills the settings from the API's config.
    applyConfig(config) {
      el('target_max_emr').value = percentInputValue(config.target_emr_rate_default);
      el(rateId).value = percentInputValue(config.irmaa_inflation_default);
    },

    // Connects the card's controls; any change asks again with the last request.
    wire() {
      ['target_max_emr', 'target_include_irmaa', 'target_irmaa_enrollees', adjustId, rateId]
        .forEach((id) => el(id).addEventListener('change', refresh));
      el(adjustId).addEventListener('change', () => {
        el(wrapId).classList.toggle('hidden', !el(adjustId).checked);
      });
      el('target-toggle').addEventListener('change', onChange);
      el('target_show_over').addEventListener('change', () => {
        renderTable();
        onChange();
      });
    },

    // Asks for the targets of a new calculation and fills the table. `sweepMaxMagi` is the
    // highest IRMAA MAGI the sweep reaches, for the reminder about tiers above it.
    async load(newRequest, sweepMaxMagi = null) {
      request = newRequest;
      sweepMax = sweepMaxMagi;
      await fetchTargets();
      renderTable();
    },

    show() {
      el('target-points-section').style.display = 'block';
    },

    // Chart pieces for the markers, or nothing while they are off or not loaded.
    overlay() {
      if (!el('target-toggle')?.checked || !targets) {
        return { traces: [], shapes: [], annotations: [] };
      }
      return targetChartMarkers(targets, el('target_show_over').checked);
    },

    // The IRMAA thresholds to draw: those the targets were placed with, else `published`.
    irmaaThresholds(published) {
      return targets?.irmaa_thresholds?.length ? targets.irmaa_thresholds : published;
    },

    // " (est. year)" for a line whose threshold was grown to the year it is billed.
    irmaaSuffix(taxYear, lookbackYears) {
      const grown = targets?.irmaa_thresholds?.length && grownBy > 0;
      return grown ? ` (est. ${taxYear + lookbackYears})` : '';
    },
  };
}
