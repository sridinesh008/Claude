---
name: parse-trace
description: Diagnose Playwright test failure from a trace.zip — routes to correct heal skill
mode: agent
tools:
  - terminal
---

## Open trace

```bash
npx playwright show-trace test-results/<test-name>/trace.zip
```

Trace path is in `.healbot-triage.json` → `unknown` category items.

## Findings → fix routing

| Finding | Route |
|---------|-------|
| Wrong locator / element not found | `#heal-locator` |
| Timeout / navigation / detached | `#heal-rewrite` |
| Network error / 4xx / 5xx | Check API mock or `waitForResponse` |
| Assertion mismatch (text/value) | Fix expected value or add `{ timeout }` |
| Snapshot diff | Re-run `node scripts/healbot-triage.js` |

## Output

```
Trace: <path>
Root cause: <one sentence>
Evidence: <screenshot timestamp or network call>
Route: <#heal-locator|#heal-rewrite|manual fix>
```

> Note: If trace not generated, add `--trace=on-first-retry` to Playwright config or CLI.
> Note: `unknown` failures with no trace → add `retries: 1` in `playwright.config.ts`.
