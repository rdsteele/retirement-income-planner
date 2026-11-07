// Tests for api/static/js/config.js

test('loadAppConfig returns the /api/config payload', async () => {
  const server = new FakeServer();
  server.handle('GET', '/api/config', () => ({ status: 200, body: { y_axis_max_emr: 0.5 } }));
  assertEqual(await loadAppConfig(), { y_axis_max_emr: 0.5 });
});

test('loadAppConfig rejects when the server fails', async () => {
  const server = new FakeServer();
  server.failOn('GET', '/api/config', 500);
  await assertRejects(loadAppConfig(), (e) => e.status === 500);
});

test('populateFilingStatuses fills the dropdown from the API and selects the first status', () => {
  const dom = installFakeDocument();
  populateFilingStatuses([
    { value: 'alpha', label: 'Alpha', filers: 1 },
    { value: 'beta', label: 'Beta', filers: 2 },
  ]);
  assertEqual(
    dom.filing_status.children.map((o) => [o.value, o.textContent, o.selected]),
    [['alpha', 'Alpha', true], ['beta', 'Beta', false]],
  );
});

test('the spouse age checkbox shows only for a status with more than one filer', async () => {
  const dom = installFakeDocument();
  populateFilingStatuses([
    { value: 'alpha', label: 'Alpha', filers: 1 },
    { value: 'beta', label: 'Beta', filers: 2 },
  ]);
  assertEqual(dom['spouse-65-wrap'].classList.contains('hidden'), true);
  dom.filing_status.value = 'beta';
  await dom.filing_status.dispatch('change');
  assertEqual(dom['spouse-65-wrap'].classList.contains('hidden'), false);
});

test('ageFlags reads both checkboxes, and setAgeFlags restores them', () => {
  installFakeDocument();
  document.getElementById('taxpayer_65_plus').type = 'checkbox';
  document.getElementById('spouse_65_plus').type = 'checkbox';
  assertEqual(ageFlags(), { taxpayer_65_plus: false, spouse_65_plus: false });
  setAgeFlags({ taxpayer_65_plus: true, spouse_65_plus: true });
  assertEqual(ageFlags(), { taxpayer_65_plus: true, spouse_65_plus: true });
});

test('loadTaxYears fills the dropdown and selects the default year from the API', async () => {
  const dom = installFakeDocument();
  const server = new FakeServer();
  server.handle('GET', '/api/tax-years', () => ({
    status: 200,
    body: { years: [2031, 2032], default_year: 2032 },
  }));
  await loadTaxYears();
  assertEqual(dom.tax_year.children.map((o) => [o.value, o.selected]), [[2031, false], [2032, true]]);
});

test('loadTaxYears rejects when the server fails', async () => {
  installFakeDocument();
  const server = new FakeServer();
  server.failOn('GET', '/api/tax-years', 500);
  await assertRejects(loadTaxYears(), (e) => e.status === 500);
});

test('selectedFilingStatus returns the chosen value', () => {
  installFakeDocument();
  el('filing_status').value = 'beta';
  assertEqual(selectedFilingStatus(), 'beta');
});

test('selectedFilingStatus throws instead of guessing when nothing is loaded', () => {
  installFakeDocument();
  let message = null;
  try {
    selectedFilingStatus();
  } catch (e) {
    message = e.message;
  }
  assertTrue(message !== null && /not loaded/.test(message), 'expected a "not loaded" error');
});

test('selectedTaxYear parses the chosen year', () => {
  installFakeDocument();
  el('tax_year').value = '2032';
  assertEqual(selectedTaxYear(), 2032);
});

test('selectedTaxYear throws instead of guessing when nothing is loaded', () => {
  installFakeDocument();
  let message = null;
  try {
    selectedTaxYear();
  } catch (e) {
    message = e.message;
  }
  assertTrue(message !== null && /not loaded/.test(message), 'expected a "not loaded" error');
});
