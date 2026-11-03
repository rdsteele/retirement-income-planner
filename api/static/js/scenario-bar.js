'use strict';

// The scenario bar shared by every page: the loaded scenario's name, the status line,
// loading the current scenario into a page, and saving the page to a scenario.
// Depends on api.js and common.js. Declarations only: nothing runs at load time.
//
// A page supplies only what is specific to it:
//   - a populate(scenario, name) callback for loading, and
//   - a gather() function for saving that returns
//     { shared: { inputs, aca, ohio }, page: { ...page-specific sections } }.

// Format version stored in every scenario file (the import check requires it).
const SCENARIO_FORMAT_VERSION = '1.0';

// The name of the loaded scenario, or null.
let currentScenarioName = null;

let _scenarioStatusTimer = null;

function updateScenarioBar() {
  const display = el('scenario-name-display');
  if (display) {
    display.textContent = currentScenarioName ? '📋 ' + currentScenarioName : '📋 No scenario loaded';
  }
  const saveButton = el('save-btn');
  if (saveButton) saveButton.disabled = !currentScenarioName;
}

// Shows the result of a scenario action in the bar. Success messages fade after a few
// seconds; errors stay until the next action.
function setScenarioStatus(message, isError = false) {
  const status = el('scenario-status');
  if (!status) return;
  clearTimeout(_scenarioStatusTimer);
  status.textContent = message;
  status.className = 'scenario-status ' + (isError ? 'error' : 'ok');
  if (!isError && message) {
    _scenarioStatusTimer = setTimeout(() => {
      status.textContent = '';
    }, 3000);
  }
}

// ── Scenario files ────────────────────────────────────────────────────────

function scenarioTimestamp() {
  return new Date().toISOString().slice(0, 19);
}

function newEmptyScenario(name) {
  return {
    name,
    saved_at: scenarioTimestamp(),
    version: SCENARIO_FORMAT_VERSION,
    inputs: {},
    ohio: {},
    aca: {},
    emr_settings: {},
    income_planning: {},
  };
}

// Merges what the page gathered into the stored scenario, keeping the sections that
// belong to other pages.
function buildScenarioData(name, existing, gathered) {
  const { shared, page } = gathered;
  return {
    ...existing,
    name,
    saved_at: scenarioTimestamp(),
    version: SCENARIO_FORMAT_VERSION,
    inputs: { ...(existing.inputs || {}), ...shared.inputs },
    aca: { ...(existing.aca || {}), ...shared.aca },
    ohio: { ...(existing.ohio || {}), ...shared.ohio },
    ...page,
  };
}

// ── Loading ───────────────────────────────────────────────────────────────

// Loads the current scenario and hands it to populate(scenario, name), which may be
// async. Resolves true when there is nothing to load or loading worked, and false
// when it failed. On failure the displayed name is cleared (so Save cannot overwrite
// the stored scenario with a blank form) and the error is shown in the bar.
async function loadCurrentScenario(populate) {
  try {
    currentScenarioName = await fetchCurrentScenarioName();
    updateScenarioBar();
    if (!currentScenarioName) return true;
    const scenario = await fetchScenarioOrNull(currentScenarioName);
    if (scenario === null) throw new Error('scenario file not found');
    await populate(scenario, currentScenarioName);
    return true;
  } catch (err) {
    const failedName = currentScenarioName;
    currentScenarioName = null;
    updateScenarioBar();
    setScenarioStatus(
      failedName
        ? `Could not load "${failedName}": ${err.message}`
        : `Could not check for a current scenario: ${err.message}`,
      true,
    );
    return false;
  }
}

// ── Saving ────────────────────────────────────────────────────────────────

async function saveCurrentScenario(gather) {
  if (!currentScenarioName) return;
  const name = currentScenarioName;
  try {
    const existing = await fetchScenarioOrNull(name);
    await saveScenarioFile(name, buildScenarioData(name, existing || {}, gather()));
    setScenarioStatus(`Saved "${name}"`);
  } catch (err) {
    setScenarioStatus(`Could not save "${name}": ${err.message}`, true);
  }
}

async function saveAsScenario(gather) {
  const name = prompt('Enter scenario name:');
  if (!name || !name.trim()) return;
  const trimmed = name.trim();
  try {
    const existing = await fetchScenarioOrNull(trimmed);
    if (existing && !confirm(`"${trimmed}" already exists. Overwrite?`)) return;
    await saveScenarioFile(trimmed, buildScenarioData(trimmed, existing || {}, gather()));
  } catch (err) {
    setScenarioStatus(`Could not save "${trimmed}": ${err.message}`, true);
    return;
  }
  try {
    await setCurrentScenarioName(trimmed);
    currentScenarioName = trimmed;
    updateScenarioBar();
    setScenarioStatus(`Saved "${trimmed}"`);
  } catch (err) {
    setScenarioStatus(
      `Saved "${trimmed}", but could not make it the current scenario: ${err.message}`,
      true,
    );
  }
}

// Connects the Save and Save As buttons, for pages that have them.
function wireScenarioButtons(gather) {
  el('save-btn')?.addEventListener('click', () => saveCurrentScenario(gather));
  el('save-as-btn')?.addEventListener('click', () => saveAsScenario(gather));
}
