#!/usr/bin/env node
const { execSync } = require('child_process');
const fs = require('fs');

const args = process.argv.slice(2);
const lastFailed = args.includes('--last-failed');
const dryRun = args.includes('--dry-run');
const fileArg = args.find(a => a.startsWith('--file='))?.split('=')[1] ?? '';

const REPORT_PATH = '.healbot-report.json';
const TRIAGE_PATH = '.healbot-triage.json';

function classifyError(err, retry, status) {
  if (/toMatchSnapshot|toHaveScreenshot/i.test(err)) return 'snapshot';
  if (retry > 0 && status === 'passed') return 'flaky';
  if (/locator|strict mode|not found|no element|selector did not match/i.test(err)) return 'locator';
  if (/timeout|navigation|detached|load state/i.test(err)) return 'timing';
  return 'unknown';
}

function walkSuites(suites, failures = []) {
  for (const suite of suites) {
    for (const spec of suite.specs ?? []) {
      for (const test of spec.tests ?? []) {
        const result = test.results?.[test.results.length - 1];
        if (!result || result.status === 'passed') continue;
        const err = result.errors?.map(e => e.message).join('\n') ?? '';
        failures.push({
          title: spec.title,
          file: spec.file,
          category: classifyError(err, result.retry ?? 0, result.status),
          retry: result.retry ?? 0,
          status: result.status,
          error: err.slice(0, 300),
        });
      }
    }
    if (suite.suites) walkSuites(suite.suites, failures);
  }
  return failures;
}

function fixSnapshots(failures) {
  const files = [...new Set(failures.filter(f => f.category === 'snapshot').map(f => f.file))];
  for (const file of files) {
    console.log(`[snapshot] Updating: ${file}`);
    if (!dryRun) execSync(`npx playwright test "${file}" --update-snapshots`, { stdio: 'inherit' });
  }
}

function writeTriage(failures) {
  const aiNeeded = failures.filter(f => f.category !== 'snapshot');
  const { snapshot, flaky, locator, timing, unknown } = aiNeeded.reduce((acc, f) => {
    acc[f.category] = (acc[f.category] ?? []);
    acc[f.category].push(f);
    return acc;
  }, {});
  fs.writeFileSync(TRIAGE_PATH, JSON.stringify({ snapshot: failures.length - aiNeeded.length, flaky, locator, timing, unknown }, null, 2));
  return aiNeeded;
}

function printSummary(failures, aiNeeded) {
  const counts = { snapshot: 0, flaky: 0, locator: 0, timing: 0, unknown: 0 };
  failures.forEach(f => counts[f.category]++);
  console.log(`\nTotal: ${failures.length} | Snapshot: ${counts.snapshot} (auto-fixed) | AI needed: ${aiNeeded.length}`);
  aiNeeded.forEach((f, i) => console.log(`  ${i + 1}. [${f.category}] ${f.title}`));
}

// --- main ---
const pwArgs = [
  '--reporter=json',
  `--output=${REPORT_PATH}`,
  '--retries=1',
  lastFailed ? '--last-failed' : '',
  fileArg ? `"${fileArg}"` : '',
].filter(Boolean).join(' ');

console.log('Running Playwright...');
try {
  execSync(`npx playwright test ${pwArgs}`, { stdio: 'inherit' });
} catch {
  // non-zero exit expected when tests fail
}

const report = JSON.parse(fs.readFileSync(REPORT_PATH, 'utf8'));
const failures = walkSuites(report.suites ?? []);

if (!failures.length) {
  console.log('All tests passed. Nothing to heal.');
  process.exit(0);
}

fixSnapshots(failures);
const aiNeeded = writeTriage(failures);
printSummary(failures, aiNeeded);

if (aiNeeded.length) console.log(`\nTriage saved: ${TRIAGE_PATH}\nNow use @healbot in Copilot Chat.`);
