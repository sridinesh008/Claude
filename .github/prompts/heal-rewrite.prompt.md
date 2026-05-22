---
name: heal-rewrite
description: Full Playwright test rewrite for timing, flaky, navigation, iframe, or network failures (Stage 2)
mode: agent
tools:
  - search/codebase
---

## Triggers

Use when `#heal-locator` failed, or `.healbot-triage.json` has `timing` / `flaky` failures.

## Strategies

**1. Hard wait → condition wait**
```ts
// before
await page.waitForTimeout(2000);
// after
await page.waitForSelector('[data-loaded]');
```

**2. Navigation**
```ts
await Promise.all([page.waitForNavigation(), page.click('a')]);
// or
await page.click('a');
await page.waitForURL('**/target');
```

**3. API assertion over UI polling**
```ts
await expect(page.getByRole('status')).toHaveText('Saved', { timeout: 10000 });
```

**4. Overlay / modal blocking click**
```ts
await page.getByRole('dialog').waitFor({ state: 'hidden' });
await page.getByRole('button', { name: 'Submit' }).click();
```

**5. Detached element**
```ts
const btn = page.getByRole('button', { name: 'Save' });
await btn.waitFor({ state: 'attached' });
await btn.click();
```

**6. iframe**
```ts
const frame = page.frameLocator('#iframe-id');
await frame.getByRole('button', { name: 'OK' }).click();
```

**7. Animation / transition**
```ts
await page.getByRole('menu').waitFor({ state: 'visible' });
await expect(page.getByRole('menu')).toBeVisible();
```

**8. Order dependency → `beforeEach` isolation**
```ts
test.beforeEach(async ({ page }) => {
  await page.goto('/reset');
});
```

## Flaky category → fix

| Category | Fix |
|----------|-----|
| race condition | `waitForResponse` / `waitForRequest` |
| animation | `waitFor({ state: 'visible' })` + `toBeVisible()` |
| auth expiry | refresh token in `beforeEach` |
| test order | isolate state in `beforeEach` |
