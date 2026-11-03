// Portable JavaScript test harness for the shared scripts in api/static/js.
//
// This file is loaded after the shared scripts and before the *.test.js files, in
// one global scope, by either runner (run-node.js in CI, run_jsc.py on macOS). It
// must not use require(), import, or any Node- or browser-only API.

const __tests = [];

function test(name, fn) {
  __tests.push({ name, fn });
}

class AssertionError extends Error {
  constructor(message) {
    super(message);
    this.name = 'AssertionError';
  }
}

function assertTrue(condition, message) {
  if (!condition) throw new AssertionError(message || 'expected a truthy value');
}

function assertEqual(actual, expected, message) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    throw new AssertionError((message ? message + ': ' : '') + `expected ${e} but got ${a}`);
  }
}

// Passes when the promise rejects and the optional predicate accepts the error.
async function assertRejects(promise, predicate, message) {
  let rejected = false;
  let error = null;
  try {
    await promise;
  } catch (err) {
    rejected = true;
    error = err;
  }
  if (!rejected) throw new AssertionError((message || 'expected a rejection') + ' (it resolved)');
  if (predicate && !predicate(error)) {
    throw new AssertionError((message || 'rejection did not match') + `: got ${error && error.message}`);
  }
}

async function __runAll() {
  const results = [];
  for (const t of __tests) {
    try {
      await t.fn();
      results.push({ name: t.name, ok: true, error: null });
    } catch (err) {
      results.push({ name: t.name, ok: false, error: String((err && err.message) || err) });
    }
  }
  return results;
}

// ── Fake DOM ──────────────────────────────────────────────────────────────

function makeFakeElement(id, tag) {
  const listeners = {};
  const classes = new Set();
  const element = {
    id,
    tagName: tag || 'div',
    textContent: '',
    className: '',
    value: '',
    placeholder: '',
    checked: false,
    disabled: false,
    selected: false,
    style: {},
    dataset: {},
    children: [],
    // Layout measurements and the Plotly-attached layout a browser would provide.
    offsetWidth: 800,
    offsetHeight: 400,
    clientWidth: 800,
    clientHeight: 400,
    parentElement: { offsetWidth: 800, offsetHeight: 400, clientWidth: 800, clientHeight: 400 },
    layout: { xaxis: { range: [0, 1] } },
    classList: {
      add: (...names) => names.forEach((n) => classes.add(n)),
      remove: (...names) => names.forEach((n) => classes.delete(n)),
      toggle: (name, force) => {
        const on = force === undefined ? !classes.has(name) : Boolean(force);
        if (on) classes.add(name);
        else classes.delete(name);
        return on;
      },
      contains: (name) => classes.has(name),
    },
    appendChild(child) {
      // Like a browser <select>: the first option is chosen unless another is selected.
      if (child.tagName === 'option' && (element.children.length === 0 || child.selected)) {
        element.value = child.value;
      }
      element.children.push(child);
      return child;
    },
    removeChild(child) {
      element.children = element.children.filter((c) => c !== child);
    },
    addEventListener(type, fn) {
      (listeners[type] = listeners[type] || []).push(fn);
    },
    // Runs the element's handlers for an event; resolves when async handlers finish.
    async dispatch(type) {
      for (const fn of listeners[type] || []) await fn({ target: element, key: '' });
    },
    click() {
      return element.dispatch('click');
    },
    select() {},
    focus() {},
    setAttribute() {},
    getAttribute: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
  };
  let html = '';
  Object.defineProperty(element, 'innerHTML', {
    get: () => html,
    set: (v) => {
      html = v;
      if (v === '') element.children = [];
    },
  });
  return element;
}

// Installs a fresh global document/window/Plotly; elements are created on first
// access by id, except ids listed in options.absent, which return null like a real
// document does for an element the page does not have.
// Returns { elements, fireDocument, plotly, window }.
function installFakePage(options = {}) {
  const absent = new Set(options.absent || []);
  const elements = {};
  const documentListeners = {};
  const plotly = { calls: [] };
  const record = (name) => (...args) => plotly.calls.push({ name, args });
  globalThis.document = {
    body: makeFakeElement('body'),
    getElementById(id) {
      if (absent.has(id)) return null;
      if (!elements[id]) elements[id] = makeFakeElement(id);
      return elements[id];
    },
    createElement: (tag) => makeFakeElement(null, tag),
    querySelectorAll: () => [],
    querySelector: () => null,
    addEventListener(type, fn) {
      (documentListeners[type] = documentListeners[type] || []).push(fn);
    },
  };
  globalThis.window = { location: { href: '' }, addEventListener() {} };
  globalThis.Plotly = {
    newPlot: record('newPlot'),
    react: record('react'),
    relayout: record('relayout'),
    Plots: { resize: record('resize') },
  };
  // Not every engine has the full console API; pages log freely.
  globalThis.console = { log() {}, info() {}, warn() {}, error() {}, debug() {} };
  globalThis.confirm = () => true;
  globalThis.prompt = () => null;
  globalThis.URL = { createObjectURL: () => 'blob:fake', revokeObjectURL() {} };
  globalThis.Blob = class Blob {};
  return {
    elements,
    plotly,
    window: globalThis.window,
    async fireDocument(type) {
      for (const fn of documentListeners[type] || []) await fn({});
    },
  };
}

// Back-compat helper for tests that only need the element map.
function installFakeDocument() {
  return installFakePage().elements;
}

// ── Timers ────────────────────────────────────────────────────────────────

// Replaces setTimeout/clearTimeout with a recorder so tests control when timers fire.
function installFakeTimers() {
  const pending = [];
  globalThis.setTimeout = (fn) => pending.push(fn);
  globalThis.clearTimeout = () => {};
  return { runPending: () => pending.splice(0).forEach((fn) => fn()), pending };
}

// ── Fake server ───────────────────────────────────────────────────────────

function fakeResponse(status, body, jsonThrows) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => (jsonThrows ? Promise.reject(new Error('bad json')) : Promise.resolve(body)),
  };
}

// An in-memory stand-in for the API with per-request failure injection.
//   server.handle('GET', '/api/config', () => ({ status: 200, body: {...} }))
//   server.failOn('POST', '/api/scenarios', 500)   // substring match on the URL
//   server.failOn('GET', '/api/config', 0)         // 0 = network failure
// Requests with no failure or exact handler go to server.fallback(method, url, body),
// which returns { status, body } or null (null -> 404).
class FakeServer {
  constructor() {
    this.handlers = [];
    this.failures = [];
    this.calls = [];
    this.fallback = null;
    globalThis.fetch = (url, options) => this.fetch(url, options);
  }

  handle(method, path, handler) {
    this.handlers.push({ method, path, handler });
  }

  failOn(method, urlPart, status) {
    this.failures.push({ method, urlPart, status });
  }

  callsMatching(method, urlPart) {
    return this.calls.filter((c) => c.method === method && c.url.indexOf(urlPart) !== -1);
  }

  respond(result) {
    return Promise.resolve(fakeResponse(result.status, result.body));
  }

  fetch(url, options) {
    const method = (options && options.method) || 'GET';
    const body = options && options.body ? JSON.parse(options.body) : null;
    this.calls.push({ method, url: decodeURIComponent(url), body });

    for (const failure of this.failures) {
      if (failure.method === method && url.indexOf(failure.urlPart) !== -1) {
        if (failure.status === 0) return Promise.reject(new TypeError('Failed to fetch'));
        const detail = failure.status === 404 ? 'Not found' : 'disk full';
        return this.respond({ status: failure.status, body: { detail } });
      }
    }
    for (const h of this.handlers) {
      if (h.method === method && h.path === url) return this.respond(h.handler(body));
    }
    const routed = this.fallback ? this.fallback(method, url, body) : null;
    return this.respond(routed || { status: 404, body: { detail: 'Not found: ' + url } });
  }
}

// A FakeServer preloaded with the scenario endpoints, backed by an in-memory store.
function makeScenarioServer() {
  const server = new FakeServer();
  server.scenarios = {};
  server.current = null;
  server.fallback = (method, url, body) => {
    if (url === '/api/scenarios/current') {
      if (method === 'POST') server.current = body.name;
      return { status: 200, body: { name: server.current } };
    }
    if (url.indexOf('/api/scenarios/') !== 0) return null;
    const name = decodeURIComponent(url.slice('/api/scenarios/'.length));
    if (method === 'POST') {
      server.scenarios[name] = body;
      return { status: 200, body: { status: 'ok' } };
    }
    if (!(name in server.scenarios)) {
      return { status: 404, body: { detail: 'Scenario not found: ' + name } };
    }
    if (method === 'DELETE') {
      delete server.scenarios[name];
      return { status: 204, body: null };
    }
    return { status: 200, body: server.scenarios[name] };
  };
  return server;
}


// ── Page boot and app server ──────────────────────────────────────────────

// Lets pending promise continuations run (several rounds, for chained awaits).
async function settle() {
  for (let i = 0; i < 200; i++) await Promise.resolve();
}

// Runs a real page's scripts (the shared files it loads, then its inline scripts)
// in a function scope, as the browser would. __PAGES is provided by the runner.
// Afterwards __page exposes the page's top-level functions and variables (read-only)
// so tests can call or inspect them, e.g. __page.renderChart().
function bootPage(name) {
  const page = __PAGES[name];
  if (!page) throw new Error('unknown page: ' + name);
  const source = page.scripts.join('\n') + '\n' + page.inline;
  const names = new Set();
  for (const m of source.matchAll(/^ {0,2}(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/gm)) names.add(m[1]);
  for (const m of source.matchAll(/^ {0,2}(?:const|let|var)\s+([A-Za-z_$][\w$]*)/gm)) names.add(m[1]);
  const exports = [...names].map((n) => `get ${JSON.stringify(n)}() { return ${n}; }`).join(',\n');
  new Function(source + `\nglobalThis.__page = {\n${exports}\n};`)();
}

// A scenario server that also serves the app's other endpoints from the saved real
// API responses (__FIXTURES, or a modified copy passed in). Accounts are empty: tests never touch profile data.
function makeAppServer(F = __FIXTURES) {
  const server = makeScenarioServer();
  const ok = (body) => () => ({ status: 200, body });
  server.handle('GET', '/api/config', ok(F.config));
  server.handle('GET', '/api/tax-years', ok(F.tax_years));
  server.handle('GET', '/api/accounts', ok([]));
  server.handle('GET', '/api/accounts/summary', ok({
    taxable_value: 0, taxable_basis: 0, taxable_unrealized_gain: 0, traditional_balance: 0,
    roth_balance: 0, hsa_balance: 0, hsa_annual_contribution: 0, total_portfolio_value: 0,
  }));
  server.handle('GET', '/api/scenarios', () => ({
    status: 200,
    body: Object.keys(server.scenarios).map((name) => ({ name, saved_at: '2026-01-01T00:00:00' })),
  }));
  const scenarioRoutes = server.fallback;
  server.fallback = (method, url, body) => {
    if (method === 'GET' && url.endsWith('/sweep-inputs')) {
      const name = decodeURIComponent(url.slice('/api/scenarios/'.length, -'/sweep-inputs'.length));
      return name in server.scenarios
        ? { status: 200, body: F.scenario_sweep_inputs }
        : { status: 404, body: { detail: 'Scenario not found: ' + name } };
    }
    return scenarioRoutes(method, url, body);
  };
  server.handle('POST', '/api/tax', ok(F.tax));
  server.handle('POST', '/api/emr', ok(F.emr));
  server.handle('POST', '/api/income-plan/summary', ok(F.income_plan_summary));
  server.handle('POST', '/api/income-plan/calculate', ok(F.income_plan_calculate));
  return server;
}
