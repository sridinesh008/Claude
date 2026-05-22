# Copilot Instructions

Playwright (TypeScript) E2E test repo.

## Stack
- Config: `playwright.config.ts`
- Reporter: `--reporter=json` + HTML
- Traces: `--trace=on-first-retry` | Output: `./test-results/`

## HealBot
For broken/flaky tests: run `node scripts/healbot-triage.js` first, then use `@healbot`.
Skills: `#heal-locator` · `#heal-rewrite` · `#parse-trace`

## Conventions
- Tests: `**/*.spec.ts` | POMs: `tests/pages/` | Fixtures: `tests/fixtures/` | Helpers: `tests/helpers/`
- Locators: `getByRole` > `getByLabel` > `getByPlaceholder` > `getByText` > `getByTestId` > `locator()`

## Never
- `page.waitForTimeout()` — use condition-based waits
- XPath, `:nth-child`, auto-generated IDs (`#input_\d+`)
