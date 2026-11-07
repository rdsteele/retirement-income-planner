'use strict';

// Application settings that come from the API (never hardcoded in the pages):
// supported filing statuses, available tax years, and UI defaults.
// Depends on api.js and common.js. Declarations only.

function loadAppConfig() {
  return apiRequest('/api/config');
}

// People on a return per filing status, from the API's filing status list.
let filersByStatus = {};

// `statuses` is the API's [{value, label, filers}] list; the first entry is selected.
function populateFilingStatuses(statuses) {
  populateSelect('filing_status', statuses, statuses[0]?.value);
  filersByStatus = Object.fromEntries(statuses.map((s) => [s.value, s.filers]));
  el('filing_status')?.addEventListener('change', updateSpouseCheckbox);
  updateSpouseCheckbox();
}

// The spouse's age checkbox shows only for a status with more than one person filing.
function updateSpouseCheckbox() {
  const filers = filersByStatus[el('filing_status')?.value];
  el('spouse-65-wrap')?.classList.toggle('hidden', !(filers > 1));
}

// The "65 or older" checkboxes as request fields (the extra standard deduction).
function ageFlags() {
  return {
    taxpayer_65_plus: Boolean(el('taxpayer_65_plus')?.checked),
    spouse_65_plus: Boolean(el('spouse_65_plus')?.checked),
  };
}

// Restores the checkboxes from saved inputs, then fixes the spouse checkbox's visibility.
function setAgeFlags(inputs) {
  setField('taxpayer_65_plus', inputs.taxpayer_65_plus);
  setField('spouse_65_plus', inputs.spouse_65_plus);
  updateSpouseCheckbox();
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
