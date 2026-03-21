# AJIO Avasa Alert

Scrapes AJIO for AVAASA brand deals and stores the results in `deals.txt`. When Telegram is configured, new deals since the last run are sent as messages.

## Features
- Scrapes AJIO search results for AVAASA brand items.
- Filters by minimum discount percentage.
- Deduplicates products and tracks new deals based on the previous `deals.txt`.
- Optional Telegram notifications per new deal.
- Runs automatically on GitHub Actions every 30 minutes.

## Requirements
- Python 3.12+
- Playwright with the Chrome browser (`playwright install chrome --with-deps`)

## Setup
From the `ajio-avasa-alert` folder:

```bash
pip install -r requirements.txt
playwright install chrome --with-deps
```

## Configuration
Create a `config.json` file in the `ajio-avasa-alert` folder (same directory as `scraper.py`).

```json
{
  "brand": "AVAASA",
  "min_discount_pct": 70,
  "size": "L",
  "telegram_bot_token": "YOUR_BOT_TOKEN",
  "telegram_chat_ids": ["123456789"]
}
```

**Fields:**
- `brand` (string): Display-only brand name used in log output. The search query is hardcoded to AVAASA brands in the scraper.
- `min_discount_pct` (number): Minimum discount percentage to keep a product.
- `size` (string, optional): AJIO size filter (for example: `S`, `M`, `L`, `XL`). Leave empty for all sizes.
- `telegram_bot_token` (string, optional): Bot token to send notifications. Leave blank to disable.
- `telegram_chat_ids` (array, optional): List of chat IDs to notify. Leave empty to disable.

> Extra keys are ignored by the scraper, so you can keep additional config values if needed.

## Running Locally

```bash
python scraper.py
```

Outputs:
- `deals.txt`: the latest list of discounted items.
- `images/`: downloaded product images (created on demand).

### Headed vs Headless
The scraper defaults to headless mode. To run with a visible browser window:

```bash
HEADLESS=false python scraper.py
```

## GitHub Actions
The workflow file is at `.github/workflows/scraper.yml` and runs every 30 minutes.

**Required repository secrets:**
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_IDS` (JSON array, e.g. `["123456789"]`)

The workflow writes `config.json` from secrets, runs the scraper, and commits changes to `deals.txt`.

## Testing
There are currently no automated tests or linting configured for this project.

## Troubleshooting
- **`config.json` not found:** Ensure it exists in the same directory as `scraper.py`.
- **Playwright errors:** Re-run `playwright install chrome --with-deps`.
- **No Telegram messages:** Verify the bot token and chat IDs, or leave them blank to disable notifications.
