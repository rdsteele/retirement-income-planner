// Tests for api/static/js/common.js

function optionsOf(select) {
  return select.children.map((o) => ({ value: o.value, text: o.textContent, selected: o.selected }));
}

test('populateSelect builds options from {value,label} objects and selects the default', () => {
  const dom = installFakeDocument();
  populateSelect('s', [{ value: 'a', label: 'Alpha' }, { value: 'b', label: 'Beta' }], 'b');
  assertEqual(optionsOf(dom.s), [
    { value: 'a', text: 'Alpha', selected: false },
    { value: 'b', text: 'Beta', selected: true },
  ]);
});

test('populateSelect accepts plain values and matches the default as a string', () => {
  const dom = installFakeDocument();
  populateSelect('s', [10, 20, 30], '20');
  assertEqual(optionsOf(dom.s).map((o) => o.selected), [false, true, false]);
  assertEqual(optionsOf(dom.s).map((o) => o.text), [10, 20, 30]);
});

test('populateSelect replaces any existing options', () => {
  const dom = installFakeDocument();
  populateSelect('s', [1, 2], 1);
  populateSelect('s', [3], 3);
  assertEqual(optionsOf(dom.s).map((o) => o.value), [3]);
});

test('formatRatePercent trims trailing zeros', () => {
  assertEqual(
    [0.22, 0.24, 0.1, 0.125, 0.37, 0.2].map(formatRatePercent),
    ['22%', '24%', '10%', '12.5%', '37%', '20%'],
  );
});

test('escHtml escapes markup characters', () => {
  assertEqual(escHtml('<a href="x">&</a>'), '&lt;a href=&quot;x&quot;&gt;&amp;&lt;/a&gt;');
  assertEqual(escHtml(42), '42');
});

test('fmt$ rounds and groups digits', () => {
  assertEqual(fmt$(1234.5), '$1,235');
  assertEqual(fmt$(0), '$0');
});

test('fnum parses numbers and treats blank, invalid, or missing as 0', () => {
  installFakeDocument();
  el('a').value = '12.5';
  el('b').value = '';
  el('c').value = 'abc';
  assertEqual([fnum('a'), fnum('b'), fnum('c')], [12.5, 0, 0]);
});

test('setField sets values, checkboxes, and ignores null/undefined', () => {
  installFakeDocument();
  setField('x', 5);
  el('flag').type = 'checkbox';
  setField('flag', 1);
  el('keep').value = 'orig';
  setField('keep', null);
  setField('keep', undefined);
  assertEqual([el('x').value, el('flag').checked, el('keep').value], [5, true, 'orig']);
});

test('showError and clearError toggle the error banner', () => {
  installFakeDocument();
  showError('Something failed');
  assertEqual([el('error-msg').textContent, el('error-msg').style.display], ['Something failed', 'block']);
  clearError();
  assertEqual([el('error-msg').textContent, el('error-msg').style.display], ['', 'none']);
});

test('allZero is true only when every value is zero', () => {
  assertTrue(allZero([0, 0, 0]));
  assertTrue(!allZero([0, 1]));
  assertTrue(allZero([]));
});
