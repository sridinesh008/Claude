import json
import pathlib
import re
import sys
import time
import random
import datetime
import urllib.parse

import requests

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_FILE = pathlib.Path(__file__).parent / "config.json"
MAX_PAGES = 1
PAGE_SIZE = 45


def load_config():
    if not CONFIG_FILE.exists():
        sys.exit(f"[ERROR] config.json not found at {CONFIG_FILE}")
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Scraping — HTML only
# ---------------------------------------------------------------------------

def scrape_ajio(brand: str, size: str = "") -> list[dict]:
    all_products = []

    with sync_playwright() as p:
        import os
        headless = os.environ.get("HEADLESS", "true").lower() != "false"
        browser = p.chromium.launch(
            headless=headless,
            channel="chrome",   # Real Chrome bypasses Akamai TLS fingerprint check
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",  # Required for GitHub Actions / Docker
            ],
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        # Mask headless fingerprints so AJIO returns results same as headed mode
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
            window.chrome = { runtime: {} };
        """)
        page = context.new_page()

        for page_num in range(MAX_PAGES):
            query = (
                ":relevance"
                ":brand:AVAASA SET"
                ":brand:AVAASA MIX N' MATCH"
                ":discountranges:70% and above"
            )
            if size:
                query += f":verticalsizegroupformat:{size}"
            url = (
                f"https://www.ajio.com/search/"
                f"?query={urllib.parse.quote(query)}"
                f"&text=avasa"
                f"&classifier=intent"
                f"&pageNum={page_num}"
                f"&pageSize={PAGE_SIZE}"
            )

            log(f"Page {page_num}: navigating to {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40_000)
            except PlaywrightTimeoutError:
                log(f"Page {page_num}: goto timeout, skipping")
                break

            # Scroll to trigger lazy-load, then wait for product cards
            try:
                page.wait_for_timeout(3000)
                page.evaluate("window.scrollTo(0, 600)")
                page.wait_for_timeout(2000)
                page.wait_for_selector("a[href*='/p/']", timeout=20_000)
                log(f"Page {page_num}: products loaded")
            except PlaywrightTimeoutError:
                log(f"Page {page_num}: product cards not found — page title: {page.title()}")
                # Save screenshot for debugging
                page.screenshot(path=str(pathlib.Path(__file__).parent / f"debug_page{page_num}.png"))
                log(f"Page {page_num}: screenshot saved as debug_page{page_num}.png")
                break

            products = parse_html(page)

            if not products:
                log(f"Page {page_num}: no products found, stopping pagination")
                break

            log(f"Page {page_num}: {len(products)} products found")
            all_products.extend(products)

            if len(products) < PAGE_SIZE:
                break

            time.sleep(random.uniform(2, 4))

        browser.close()

    return all_products


def parse_html(page) -> list[dict]:
    """
    Parse product cards from rendered DOM.
    Image selector derived from XPath:
      /html/body/div[1]/div[2]/div/div[3]/div/div/div/div/div[2]/div[4]/div[1]
      /div/div/div[1]/div/div/a/div/div[1]/div[1]/div/img
    → a[href*="/p/"] > div > div:first-child > div:first-child > div > img
    """
    products = []
    try:
        cards = page.query_selector_all("a[href*='/p/']")
        log(f"Found {len(cards)} product card links in DOM")

        for card in cards:
            try:
                href = card.get_attribute("href") or ""
                url = "https://www.ajio.com" + href if href.startswith("/") else href
                if not url:
                    continue

                # Image — match XPath: a > div > div:first-child > div:first-child > div > img
                img_el = card.query_selector(
                    "div > div:first-child > div:first-child > div > img, "
                    "div > div:first-child img, "
                    "img"
                )
                image_url = ""
                if img_el:
                    image_url = (
                        img_el.get_attribute("src") or
                        img_el.get_attribute("data-src") or
                        img_el.get_attribute("data-lazy-src") or ""
                    )
                    # Skip placeholder/base64 images
                    if image_url.startswith("data:"):
                        image_url = img_el.get_attribute("data-src") or ""

                # Full text of the card for name + price parsing
                card_text = card.inner_text()

                # Name — first non-empty line that isn't a price
                name = "Unknown"
                for line in card_text.splitlines():
                    line = line.strip()
                    if line and not re.search(r"[₹%]|\d{3,}", line):
                        name = line
                        break

                # Prices — find all ₹ amounts
                price_matches = re.findall(r"₹\s*([\d,]+)", card_text)
                prices = [float(m.replace(",", "")) for m in price_matches]

                # Discount % — e.g. "49% off"
                disc_match = re.search(r"(\d+)\s*%", card_text)
                discount = int(disc_match.group(1)) if disc_match else 0

                if len(prices) < 2 or discount <= 0:
                    continue

                selling = min(prices[:2])
                mrp = max(prices[:2])

                if mrp <= 0 or selling <= 0:
                    continue

                # Recompute discount from prices for accuracy
                discount = round((1 - selling / mrp) * 100)
                if not (0 < discount <= 100):
                    continue

                products.append({
                    "name": name,
                    "mrp": mrp,
                    "price": selling,
                    "discount": discount,
                    "url": url,
                    "image_url": image_url,
                    "image_path": "",
                })
            except Exception:
                continue
    except Exception as e:
        log(f"[WARN] parse_html error: {e}")

    return products


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_products(products: list[dict], min_pct: int) -> list[dict]:
    return [p for p in products if p.get("discount", 0) >= min_pct]


# ---------------------------------------------------------------------------
# Image download
# ---------------------------------------------------------------------------

IMAGES_DIR = pathlib.Path(__file__).parent / "images"


def download_images(products: list[dict]):
    import urllib.request
    IMAGES_DIR.mkdir(exist_ok=True)
    for p in products:
        if not p.get("image_url"):
            continue
        code = extract_product_code(p["url"]) or str(abs(hash(p["url"])))
        ext = p["image_url"].split("?")[0].rsplit(".", 1)[-1][:4] or "jpg"
        dest = IMAGES_DIR / f"{code}.{ext}"
        if dest.exists():
            p["image_path"] = str(dest)
            continue
        try:
            urllib.request.urlretrieve(p["image_url"], dest)
            p["image_path"] = str(dest)
            log(f"Downloaded image: {dest.name}")
        except Exception as e:
            log(f"[WARN] Image download failed for {p['name']}: {e}")


# ---------------------------------------------------------------------------
# Output — text file
# ---------------------------------------------------------------------------

OUTPUT_FILE = pathlib.Path(__file__).parent / "deals.txt"


def load_known_urls() -> set[str]:
    """Read URLs from existing deals.txt to detect already-seen products."""
    if not OUTPUT_FILE.exists():
        return set()
    known = set()
    for line in OUTPUT_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("https://"):
            known.add(line)
    log(f"Known URLs from previous run: {len(known)}")
    return known


def save_to_file(products: list[dict], min_pct: int):
    today = datetime.date.today().strftime("%d %b %Y")
    lines = [
        f"AJIO Avasa Deals ({min_pct}%+ OFF) — {today}",
        f"Total: {len(products)} products",
        "=" * 60,
        "",
    ]
    for i, p in enumerate(products, 1):
        mrp_str = f"Rs.{int(p['mrp'])}"
        price_str = f"Rs.{int(p['price'])}"
        lines.append(f"{i}. {p['name']}")
        lines.append(f"   MRP: {mrp_str} | Now: {price_str} | {p['discount']}% OFF")
        lines.append(f"   {p['url']}")
        lines.append("")

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    log(f"Results saved to {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Telegram notification
# ---------------------------------------------------------------------------

def extract_product_code(url: str) -> str:
    match = re.search(r"/p/([^/?#]+)", url)
    return match.group(1) if match else ""


TG_BASE = "https://api.telegram.org/bot{token}/{endpoint}"


def send_telegram_text(token: str, chat_id: str, message: str):
    url = TG_BASE.format(token=token, endpoint="sendMessage")
    resp = requests.post(url, data={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "false",
    }, timeout=30)
    result = resp.json()
    if not result.get("ok"):
        log(f"[ERROR] Telegram sendMessage failed: {result}")


def send_telegram_photo(token: str, chat_id: str, image_url: str, caption: str):
    url = TG_BASE.format(token=token, endpoint="sendPhoto")
    resp = requests.post(url, data={
        "chat_id": chat_id,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown",
    }, timeout=30)
    result = resp.json()
    if not result.get("ok"):
        log(f"[WARN] Telegram sendPhoto failed: {result}")


def format_product_caption(p: dict, index: int, total: int) -> str:
    mrp_str = f"Rs.{int(p['mrp'])}"
    price_str = f"Rs.{int(p['price'])}"
    code = extract_product_code(p["url"])
    deep_link = f"ajio://pdp?code={code}" if code else ""
    lines = [
        f"*{index}/{total}. {p['name']}*",
        f"~~{mrp_str}~~ → {price_str} | *{p['discount']}% OFF*",
        f"[Open in Browser]({p['url']})",
    ]
    return "\n".join(lines)


def format_product_message(p: dict, index: int, total: int, min_pct: int) -> str:
    mrp_str = f"Rs.{int(p['mrp'])}"
    price_str = f"Rs.{int(p['price'])}"
    code = extract_product_code(p["url"])
    deep_link = f"ajio://pdp?code={code}" if code else ""

    # Invisible link at top forces Telegram to use this image as the link preview thumbnail
    thumb = f"[​]({p['image_url']})" if p.get("image_url") else ""

    lines = [
        f"{thumb}*{index}/{total} · {p['name']}*",
        f"~~{mrp_str}~~ → *{price_str}* | *{p['discount']}% OFF*",
        f"[Open in Browser]({p['url']})",
    ]
    if deep_link:
        lines.append(f"[Open in App]({deep_link})")
    return "\n".join(lines)


def send_telegram_all(token: str, chat_id: str, products: list[dict], min_pct: int):
    today = datetime.date.today().strftime("%d %b %Y")
    total = len(products)
    # Header message
    send_telegram_text(token, chat_id, f"*AJIO Avasa — {min_pct}%+ OFF* ({today})\n_{total} products found_")
    time.sleep(0.5)

    for i, p in enumerate(products, 1):
        message = format_product_message(p, i, total, min_pct)
        send_telegram_text(token, chat_id, message)
        log(f"Sent product {i}/{total} to {chat_id}")
        time.sleep(0.5)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cfg = load_config()
    min_pct = int(cfg.get("min_discount_pct", 80))
    brand = cfg.get("brand", "avasa")

    log(f"Starting AJIO {brand} scraper (min discount: {min_pct}%)")

    size = cfg.get("size", "")
    all_products = scrape_ajio(brand, size)

    # Deduplicate by URL
    seen = set()
    unique_products = []
    for p in all_products:
        if p["url"] not in seen:
            seen.add(p["url"])
            unique_products.append(p)
    all_products = unique_products
    log(f"Total products scraped (deduplicated): {len(all_products)}")

    deals = filter_products(all_products, min_pct)
    log(f"Products with {min_pct}%+ discount: {len(deals)}")

    # Find products not seen in the previous run
    known_urls = load_known_urls()
    new_deals = [p for p in deals if p["url"] not in known_urls]
    log(f"New deals (not in previous run): {len(new_deals)}")

    # Always save full current list so next run can diff against it
    save_to_file(deals, min_pct)

    token = cfg.get("telegram_bot_token", "")
    chat_ids = cfg.get("telegram_chat_ids", [])
    if not new_deals:
        log("No new deals — skipping notification.")
    elif token and "YOUR_BOT_TOKEN" not in token and chat_ids:
        for chat_id in chat_ids:
            log(f"Sending to chat_id {chat_id}...")
            send_telegram_all(token, chat_id, new_deals, min_pct)
    else:
        log("Telegram not configured — skipping notification.")

    log("Done.")


if __name__ == "__main__":
    main()
