'use strict';

// Small DOM, formatting, and error-banner helpers shared by every page.
// Declarations only: nothing here runs at load time.

const el = (id) => document.getElementById(id);
const fnum = (id) => parseFloat(el(id)?.value) || 0;
const fmt$ = (n) => '$' + Math.round(n).toLocaleString('en-US');
const formatRatePercent = (rate) => (rate * 100).toFixed(2).replace(/\.?0+$/, '') + '%';
const allZero = (values) => values.every((v) => v === 0);

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Replaces the select's options. `options` holds plain values or {value, label}.
function populateSelect(selectId, options, defaultValue) {
  const select = el(selectId);
  if (!select) return;
  select.innerHTML = '';
  options.forEach((opt) => {
    const option = document.createElement('option');
    option.value = opt.value ?? opt;
    option.textContent = opt.label ?? opt;
    if (String(option.value) === String(defaultValue)) option.selected = true;
    select.appendChild(option);
  });
}

function setField(id, value) {
  const field = el(id);
  if (!field || value == null) return;
  if (field.type === 'checkbox') field.checked = Boolean(value);
  else field.value = value;
}

// The page's #error-msg banner.
function showError(message) {
  const box = el('error-msg');
  if (!box) return;
  box.textContent = message;
  box.style.display = 'block';
}

function clearError() {
  const box = el('error-msg');
  if (!box) return;
  box.style.display = 'none';
  box.textContent = '';
}
