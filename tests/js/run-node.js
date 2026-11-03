// Runs the JavaScript tests under Node (used by CI). Usage: node tests/js/run-node.js
//
// Every script is evaluated in one shared global context, like <script> tags in a
// browser page: first the shared scripts, then the harness, then the test files.

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..', '..');
const sharedDir = path.join(root, 'api', 'static', 'js');

function scriptsIn(dir, suffix) {
  return fs
    .readdirSync(dir)
    .filter((name) => name.endsWith(suffix))
    .sort()
    .map((name) => path.join(dir, name));
}

const files = [
  ...scriptsIn(sharedDir, '.js'),
  path.join(__dirname, 'harness.js'),
  ...scriptsIn(__dirname, '.test.js'),
];

// Real pages (the shared scripts each loads, in order, plus its inline scripts) and
// saved real API responses, exposed to the tests as globals.
function parsePage(html) {
  const scripts = [...html.matchAll(/<script src="\/static\/js\/([^"]+)"><\/script>/g)].map((m) =>
    fs.readFileSync(path.join(sharedDir, m[1]), 'utf8'),
  );
  const inline = [...html.matchAll(/<script(?![^>]*\bsrc\b)[^>]*>([\s\S]*?)<\/script>/g)]
    .map((m) => m[1])
    .join('\n');
  return { scripts, inline };
}

const pagesDir = path.join(root, 'api', 'static');
const pages = {};
for (const name of fs.readdirSync(pagesDir).filter((n) => n.endsWith('.html'))) {
  pages[name.replace(/\.html$/, '')] = parsePage(fs.readFileSync(path.join(pagesDir, name), 'utf8'));
}
const fixturesDir = path.join(__dirname, 'fixtures');
const fixtures = {};
for (const name of fs.readdirSync(fixturesDir).filter((n) => n.endsWith('.json'))) {
  fixtures[name.replace(/\.json$/, '')] = JSON.parse(fs.readFileSync(path.join(fixturesDir, name), 'utf8'));
}

const context = vm.createContext({ console });
vm.runInContext(
  `const __PAGES = ${JSON.stringify(pages)}; const __FIXTURES = ${JSON.stringify(fixtures)};`,
  context,
);
for (const file of files) {
  vm.runInContext(fs.readFileSync(file, 'utf8'), context, { filename: file });
}

vm.runInContext('__runAll()', context).then((results) => {
  let failed = 0;
  for (const r of results) {
    if (r.ok) {
      console.log(`PASS ${r.name}`);
    } else {
      failed += 1;
      console.log(`FAIL ${r.name}\n     ${r.error}`);
    }
  }
  console.log(`\n${results.length - failed} passed, ${failed} failed`);
  process.exit(failed === 0 ? 0 : 1);
});
