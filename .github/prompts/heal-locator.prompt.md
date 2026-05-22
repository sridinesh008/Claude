---
name: heal-locator
description: Fix broken Playwright locators using semantic locator API (Stage 1)
mode: agent
tools:
  - search/codebase
---

## Triggers

Use when `.healbot-triage.json` has `locator` failures, or error contains:
`locator()` · `strict mode` · `not found` · `no element` · `selector did not match`

## Locator priority

1. `getByRole` — ARIA role + accessible name
2. `getByLabel` — form fields
3. `getByPlaceholder` — inputs
4. `getByText` — visible text (exact match preferred)
5. `getByTestId` — `data-testid` attribute
6. `getByAltText` / `getByTitle`
7. `locator()` — last resort, CSS only

## Fix patterns

**XPath → role**
```ts
// before
page.locator('//button[@class="submit"]')
// after
page.getByRole('button', { name: 'Submit' })
```

**nth-child → filter**
```ts
// before
page.locator('li:nth-child(2)')
// after
page.getByRole('listitem').filter({ hasText: 'Item Name' })
```

**Auto-ID → label**
```ts
// before
page.locator('#input_3')
// after
page.getByLabel('Email')
```

**Strict mode (multiple matches) → first/filter**
```ts
// before
page.locator('.btn')  // matches 3 elements
// after
page.getByRole('button', { name: 'Save' }).first()
```

## Escalate to `#heal-rewrite` if

- Element exists in DOM but not interactable (timing issue)
- Locator correct but inside iframe/shadow DOM
- Error persists after 2 locator fixes

## Output

```
File: <path>
Line: <number>
Before: <old locator>
After: <new locator>
Reason: <why this selector was wrong>
```
