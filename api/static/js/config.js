'use strict';

// Application settings that come from the API (never hardcoded in the pages):
// supported filing statuses, available tax years, and UI defaults.
// Depends on api.js and common.js. Declarations only.

function loadAppConfig() {
  return apiRequest('/api/config');
}

// `statuses` is the API's [{value, label}] list; the first entry is selected.
function populateFilingStatuses(statuses) {
  populateSelect('filing_status', statuses, statuses[0]?.value);
}

async function loadTaxYears() {
  const data = await apiRequest('/api/tax-years');
  populateSelect('tax_year', data.years, data.default_year);
}

// Read the dropdowns for a request. These throw, rather than fall back to a guessed
// value, when the options have not loaded.
function selectedFilingStatus() {
  const value = el('filing_status')?.value;
  if (!value) throw new Error('Filing status options are not loaded yet.');
  return value;
}

function selectedTaxYear() {
  const year = parseInt(el('tax_year')?.value, 10);
  if (Number.isNaN(year)) throw new Error('Tax year options are not loaded yet.');
  return year;
}
