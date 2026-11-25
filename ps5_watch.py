"""PS5 stock watcher (PS5 Pro and/or PS5 Digital Edition) for Canadian retailers.
Which consoles are watched is set by filters.max_price in config.yaml.

Checks each retailer once and sends an ntfy push notification when a matching
console goes from out of stock to in stock. Meant to be run every few minutes
by Windows Task Scheduler (see install_task.ps1).

Usage:
  python ps5_watch.py              one check, alerts on
  python ps5_watch.py --dry-run    one check, print every product seen, no alerts
  python ps5_watch.py --test-alert send a test notification and exit
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import quote, quote_plus

import requests
import yaml
from lxml import html as lxml_html

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "config.yaml"
STATE_FILE = HERE / "state.json"
LOG_FILE = HERE / "ps5_watch.log"
HISTORY_CSV = HERE / "stock_history.csv"
HISTORY_KEEP = 200  # restock events kept in state.json (the CSV keeps everything)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Accept-Language": "en-CA,en;q=0.9",
}
TIMEOUT = 30

log = logging.getLogger("ps5_watch")


@dataclass
class Offer:
    retailer: str
    id: str
    title: str
    price: float | None
    url: str
    in_stock: bool
    first_party: bool = True
    stock_note: str = ""


# --------------------------------------------------------------------------
# Product matching
# --------------------------------------------------------------------------

# Words that mean "a different console" (Pro / Disc) or "not new".
# Accessory words (stand, cover, dock, membership, ...) are deliberately NOT here:
# real console bundles include those things, and accessories are already stopped
# by the min_price filter (no PS5 accessory costs $300+).
EXCLUDE_PATTERNS = [
    r"\bpro\b",
    r"disc drive", r"disc edition", r"disc\s*(&|and|/)", r"(&|and|/)\s*disc",
    r"refurbished", r"renewed", r"open box", r"\bused\b", r"pre-?owned",
]
_EXCLUDE_RE = re.compile("|".join(EXCLUDE_PATTERNS))


def normalize(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[®™©]", "", t)
    t = re.sub(r"[‐-―−]", "-", t).replace("’", "'")  # all dash kinds -> "-"
    return re.sub(r"\s+", " ", t).strip()


def is_ps5_digital(title: str) -> bool:
    """True for the PS5 Digital Edition console or a bundle that includes it."""
    t = normalize(title)
    is_ps5 = bool(re.search(r"playstation\s*5|\bps5\b", t))
    return is_ps5 and "digital" in t and not _EXCLUDE_RE.search(t)


NOT_NEW_RE = re.compile(r"refurbished|renewed|open box|\bused\b|pre-?owned")


def is_ps5_pro(title: str) -> bool:
    """True for the PS5 Pro console or a bundle that includes it.
    "Pro" must come right after "PlayStation 5"/"PS5", so a "Razer ... Pro Controller - PS5"
    doesn't count. Pro accessories ("Stand for PS5 Pro") are stopped by min_price."""
    t = normalize(title)
    # also catches "PS5Pro", "PS 5 Pro" and "PlayStation 5 - Pro"
    return bool(re.search(r"(playstation\s*5|\bps\s*5)(\s*slim)?\s*[-:]?\s*pro\b", t)) and not NOT_NEW_RE.search(t)


PRODUCTS = ["PS5 Digital", "PS5 Pro"]  # every console this program knows about


def watched(cfg: dict) -> list[str]:
    """The consoles being watched: those with a price limit in config.yaml."""
    return [p for p in PRODUCTS if p in cfg["filters"]["max_price"]]


def product_of(title: str) -> str | None:
    """Which watched console a listing is: "PS5 Digital", "PS5 Pro" or None."""
    if is_ps5_pro(title):
        return "PS5 Pro"
    if is_ps5_digital(title):
        return "PS5 Digital"
    return None


def is_console_listing(offer: Offer, cfg: dict) -> bool:
    """A watched console page (any price/stock/seller), not a cheap accessory."""
    return (product_of(offer.title) in watched(cfg)
            and (offer.price is None or offer.price >= cfg["filters"]["min_price"]))


def passes_filters(offer: Offer, cfg: dict) -> tuple[bool, str]:
    f = cfg["filters"]
    product = product_of(offer.title)
    if product not in f["max_price"]:
        return False, "not a watched console"
    if offer.price is None:
        # In stock but the price couldn't be read: alert anyway (price shows as "?")
        # rather than risk missing a restock. Check the price on the page.
        ok = not (f.get("first_party_only", True) and not offer.first_party)
        return ok, "price unknown" if ok else "marketplace seller"
    if not (f["min_price"] <= offer.price < f["max_price"][product]):
        return False, f"price ${offer.price:,.2f} out of range"
    if f.get("first_party_only", True) and not offer.first_party:
        return False, "marketplace seller"
    return True, "match"


def parse_price(text) -> float | None:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(text))
    return float(m.group(0).replace(",", "")) if m else None


# --------------------------------------------------------------------------
# Retailers
# --------------------------------------------------------------------------

# Best Buy stores checked for in-store pickup: the 42 stores Best Buy itself lists
# as nearby for Montreal (island, Laval, South Shore, North Shore, West Island).
BESTBUY_PICKUP_STORES = (
    "270|967|274|286|252|288|651|280|268|276|301|264|269|284|279|273|969|962|282|281|251|"
    "84|283|971|305|265|968|266|272|970|285|681|311|978|297|267|663|290|298|287|674|296"
)


# Search words per store and console. Only the watched consoles' searches are run.
SEARCHES = {
    "bestbuy": {"PS5 Digital": ("ps5 digital edition", "playstation 5 digital edition bundle"),
                "PS5 Pro": ("ps5 pro console", "playstation 5 pro bundle")},
    "canadacomputers": {p: (p,) for p in ("PS5 Digital", "PS5 Pro")},  # products, not search words
    "walmart": {"PS5 Digital": ("ps5 digital edition",), "PS5 Pro": ("ps5 pro console",)},
    "amazon": {"PS5 Digital": ("playstation 5 digital edition console",),
               "PS5 Pro": ("playstation 5 pro console",)},
}


def queries_for(key: str, cfg: dict) -> tuple[str, ...]:
    return tuple(q for p in watched(cfg) for q in SEARCHES.get(key, {}).get(p, ()))


def check_bestbuy(session: requests.Session, queries=("ps5 digital edition", "ps5 pro console")) -> list[Offer]:
    """Best Buy Canada: the site's own JSON search + availability endpoints."""
    if isinstance(queries, str):
        queries = (queries,)
    products: dict[str, dict] = {}
    for query in queries:
        r = session.get("https://www.bestbuy.ca/api/v2/json/search",
                        params={"query": query, "lang": "en-CA", "pageSize": 48},
                        timeout=TIMEOUT)
        r.raise_for_status()
        for p in r.json().get("products", []):
            products[p["sku"]] = p

    if not products:
        raise RuntimeError("Best Buy search returned no products (format changed?)")

    offers = {}
    for sku, p in products.items():
        offers[sku] = Offer(
            retailer="Best Buy",
            id=sku,
            title=p.get("name", ""),
            price=parse_price(p.get("salePrice") or p.get("regularPrice")),
            url="https://www.bestbuy.ca" + p.get("productUrl", ""),
            in_stock=False,
            first_party=not p.get("isMarketplace", False),
        )

    # Only look up stock for consoles (not $40 stands) - keeps requests small.
    skus = [s for s, o in offers.items() if product_of(o.title) and (o.price is None or o.price >= 300)]
    if skus:
        r = session.get("https://www.bestbuy.ca/ecomm-api/availability/products",
                        params={"accept": "application/vnd.bestbuy.standardproduct.v1+json",
                                "accept-language": "en-CA", "skus": "|".join(skus),
                                "locations": BESTBUY_PICKUP_STORES},
                        timeout=60)
        r.raise_for_status()
        for a in r.json().get("availabilities", []):
            o = offers.get(str(a.get("sku")))
            if not o:
                continue
            ship = a.get("shipping") or {}
            pickup = a.get("pickup") or {}
            stores = [l.get("name", "?") for l in pickup.get("locations") or []
                      if l.get("hasInventory") and (l.get("quantityOnHand") or 0) > 0]
            online_ok = bool(ship.get("purchasable"))
            pickup_ok = bool(pickup.get("purchasable")) and bool(stores)
            o.in_stock = online_ok or pickup_ok
            o.stock_note = f"online: {ship.get('status')}, Montreal-area pickup: {pickup.get('status')}"
            if pickup_ok:
                shown = ", ".join(stores[:5]) + (f" +{len(stores) - 5} more" if len(stores) > 5 else "")
                o.stock_note += f" at {len(stores)} store(s): {shown}"
            if a.get("sellerId") and a["sellerId"] != "bbyca":
                o.first_party = False
    return list(offers.values())


# Canada Computers' PlayStation category lists every PlayStation console (Digital, Pro,
# bundles). We read it instead of the site search: one page per check, and the search
# page started refusing this connection (403) after a few hours of 5-minute checks.
CC_PLAYSTATION_PAGE = "https://www.canadacomputers.com/en/877/playstation"


def check_canadacomputers(session: requests.Session, queries=None) -> list[Offer]:
    """queries = the watched consoles, whose Montreal store stock is looked up when
    sold out online (default: all). The one category page covers every console."""
    products = set(queries or PRODUCTS)
    cards = []
    for url in (CC_PLAYSTATION_PAGE,):
        r = session.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        doc = lxml_html.fromstring(r.text)
        found = doc.xpath("//div[contains(@class,'js-product') and starts-with(@id,'product_card_')]")
        if not found and "product-miniature" not in r.text:
            raise RuntimeError("Canada Computers page had no product cards (blocked or format changed?)")
        cards += found

    offers, seen = [], set()
    for card in cards:
        if card.get("id") in seen:
            continue
        seen.add(card.get("id"))
        link = card.xpath(".//h2[contains(@class,'product-title')]/a")
        if not link:
            continue
        title = link[0].text_content().strip()
        url = (link[0].get("content") or link[0].get("href") or "").split("?")[0]
        desc = card.xpath(".//div[contains(@class,'product-description')]")
        price = parse_price(desc[0].get("data-final_price")) if desc else None

        tag = card.xpath(".//div[contains(@class,'available-tag')]")
        lines = [re.sub(r"\s+", " ", t).strip() for t in (tag[0].itertext() if tag else [])]
        lines = [l for l in lines if l]
        online = next((l for l in lines if "online" in l.lower()), "")
        online_ok = bool(online) and not re.search(r"sold out|not available|unavailable", online.lower())

        offer = Offer(
            retailer="Canada Computers",
            id=card.get("id", "").replace("product_card_", ""),
            title=title, price=price, url=url,
            in_stock=online_ok,
            stock_note=" | ".join(lines),
        )
        # Sold out online? The product page lists stock at every store - look at Montreal's.
        # (Only for watched consoles; accessories under $300 can never trigger an alert.)
        if (not online_ok and product_of(title) in products and url
                and (price is None or price >= 300)):
            try:
                stores = cc_montreal_stock(session, url)
            except Exception as e:
                log.warning("Canada Computers store stock lookup failed for %s: %s", title, e)
                offer.stock_note += " | Montreal store stock: could not check"
                stores = {}
            if stores:
                offer.in_stock = True
                offer.stock_note = ("online: sold out, Montreal-area pickup: "
                                    + ", ".join(f"{n} at {s}" for s, n in stores.items()))
        offers.append(offer)
    return offers


CC_MONTREAL_STORES = ("Montreal", "Brossard", "Marche Central", "Laval")


def cc_montreal_stock(session: requests.Session, url: str) -> dict[str, int]:
    """Units on the shelf at Montreal-area Canada Computers stores, e.g. {"Brossard": 4}."""
    r = session.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    doc = lxml_html.fromstring(r.text)
    box = doc.xpath("//*[@id='checkothertores']")
    if not box:
        raise RuntimeError(f"Canada Computers product page had no store list (format changed?): {url}")
    stock = {}
    for name_el in box[0].xpath(".//span[contains(@class,'col-3')]"):
        name = name_el.text_content().strip()
        count = name_el.xpath("following-sibling::span[contains(@class,'shop-online-box')][1]")
        if name in CC_MONTREAL_STORES and count:
            n = int(re.sub(r"\D", "", count[0].text_content()) or 0)
            if n > 0:
                stock[name] = n
    return stock


# ---- Browser-based retailers ---------------------------------------------
# These sites block plain HTTP requests, so they are loaded in a normal, visible
# Microsoft Edge window driven by Playwright. If a site shows a bot check / CAPTCHA
# we do NOT try to get past it: the check just counts as failed.

AMAZON_CA_SELLER_ID = "A3DWYIK6Y9EEQB"  # Amazon.ca itself (excludes marketplace sellers)


def _load(page, url: str, wait_ms: int = 5000) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(wait_ms)
    # Cloudflare's "Just a moment..." page normally finishes on its own in a few
    # seconds; give it time, but never interact with it.
    for _ in range(10):
        if "just a moment" not in page.title().lower():
            break
        page.wait_for_timeout(2000)
    if re.search(r"just a moment|robot check|access denied", page.title().lower()):
        raise RuntimeError(f"blocked by a bot check ({page.title()!r})")


def _combine(search, page, queries) -> list[Offer]:
    """Run one search per query and merge the results (no duplicates)."""
    if isinstance(queries, str):
        queries = (queries,)
    offers = {}
    for q in queries:
        for o in search(page, q):
            offers.setdefault(o.id, o)
    return list(offers.values())


def check_walmart(page, queries=("ps5 digital edition", "ps5 pro console")) -> list[Offer]:
    return _combine(_walmart_search, page, queries)


def check_amazon(page, queries=("playstation 5 digital edition console", "playstation 5 pro console")) -> list[Offer]:
    return _combine(_amazon_search, page, queries)


def _walmart_search(page, query: str) -> list[Offer]:
    _load(page, "https://www.walmart.ca/en/search?q=" + quote(query))
    if "/blocked" in page.url:
        raise RuntimeError("blocked by Walmart's bot check")
    raw = page.evaluate("() => document.getElementById('__NEXT_DATA__')?.textContent || ''")
    if not raw:
        raise RuntimeError("Walmart page had no product data (format changed?)")

    items = []

    def walk(o):
        if isinstance(o, dict):
            if "usItemId" in o and "name" in o:
                items.append(o)
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(json.loads(raw))
    offers = []
    for it in items:
        price = parse_price(it.get("price"))
        if price is None and isinstance(it.get("priceInfo"), dict):
            price = parse_price(it["priceInfo"].get("linePrice"))
        seller = it.get("sellerName") or ""
        status = it.get("availabilityStatusDisplayValue") or ""
        offers.append(Offer(
            retailer="Walmart",
            id=str(it.get("usItemId")),
            title=it.get("name", ""),
            price=price,
            url="https://www.walmart.ca" + (it.get("canonicalUrl") or "").split("?")[0],
            in_stock=not it.get("isOutOfStock", True),
            first_party=seller.strip().lower() in ("walmart", "walmart.ca", "walmart canada"),
            stock_note=f"{status}; sold by {seller or '?'}",
        ))
    return offers


def _amazon_search(page, query: str) -> list[Offer]:
    # rh=p_6:<id> limits results to items sold by Amazon.ca itself. Out-of-stock
    # consoles simply don't appear, so anything listed here with a price is buyable.
    _load(page, f"https://www.amazon.ca/s?k={quote_plus(query)}&rh=p_6%3A{AMAZON_CA_SELLER_ID}")
    doc = lxml_html.fromstring(page.content())
    if doc.xpath("//form[contains(@action,'validateCaptcha')]"):
        raise RuntimeError("Amazon showed a CAPTCHA")
    cards = doc.xpath("//div[@data-component-type='s-search-result']")
    if not cards and "no results for" not in page.content().lower():
        raise RuntimeError("Amazon page had no search results (format changed?)")

    offers = []
    for c in cards:
        asin = c.get("data-asin")
        title = " ".join(c.xpath(".//h2//text()")).strip()
        prices = c.xpath(".//span[contains(@class,'a-price')]/span[@class='a-offscreen']/text()")
        text = re.sub(r"\s+", " ", c.text_content())
        unavailable = re.search(r"currently unavailable|no featured offers", text, re.I)
        # Sponsored ads don't necessarily respect the "sold by Amazon.ca" filter.
        sponsored = "AdHolder" in (c.get("class") or "") or re.search(r"\bSponsored\b", text)
        offers.append(Offer(
            retailer="Amazon.ca",
            id=asin,
            title=title,
            price=parse_price(prices[0]) if prices else None,
            url=f"https://www.amazon.ca/dp/{asin}",
            in_stock=bool(prices) and not unavailable,
            first_party=not sponsored,
            stock_note=("sponsored ad, seller unknown" if sponsored else "sold by Amazon.ca")
                       + ("; unavailable" if unavailable else ""),
        ))
    return offers


# Staples sits behind Cloudflare, which blocks more often the more pages we load,
# so we open only these product pages directly (one page per check) instead of
# searching. Add a URL here if Staples lists a new PS5 bundle. Only the watched
# consoles' pages are opened.
STAPLES_PRODUCTS = {
    "PS5 Digital": ("https://www.staples.ca/products/3140351-en-sony-playstation-5-digital-edition-console",),
    "PS5 Pro": ("https://www.staples.ca/products/3103551-en-sony-playstation-5-pro-console",),
}
SEARCHES["staples"] = STAPLES_PRODUCTS  # "searches" here are the product page URLs


def check_staples(page, queries=None) -> list[Offer]:
    """queries = product page URLs (default: every page in STAPLES_PRODUCTS)."""
    if isinstance(queries, str):
        queries = (queries,)
    urls = queries or [u for us in STAPLES_PRODUCTS.values() for u in us]
    offers = []
    for url in urls:
        _load(page, url, wait_ms=4000)
        try:
            page.wait_for_load_state("load", timeout=15000)
        except Exception:
            pass  # slow ads/trackers; the stock-info wait below is what matters
        title = re.sub(r"\s*\|\s*staples\.ca\s*$", "", page.title(), flags=re.I).strip()
        offer = Offer("Staples", url.rsplit("/", 1)[-1].split("-")[0], title, None, url, False)
        offers.append(offer)

        # Price from Shopify's product JSON. Its "available" flag is NOT trusted:
        # it says true even when the console is sold out.
        info = page.evaluate("async (u) => { const r = await fetch(u + '.js'); return r.ok ? r.json() : null; }",
                             offer.url)
        if info and info.get("price") is not None:
            offer.price = info["price"] / 100
            offer.title = info.get("title") or offer.title

        # Real online stock: product page says "Delivery available" when it can ship.
        try:
            page.wait_for_function(
                "() => document.body.innerText.includes('Ways to get your order')", timeout=20000)
        except Exception:
            raise RuntimeError(f"Staples product page never showed stock info: {offer.url}")
        page.wait_for_timeout(1500)  # let the delivery/pickup lines fill in
        body = page.evaluate("() => document.body.innerText")
        i = body.find("Ways to get your order")
        section = re.sub(r"\s+", " ", body[i:i + 300])
        offer.in_stock = "delivery available" in section.lower()
        offer.stock_note = section[len("Ways to get your order"):].strip()[:120]
    return offers


HTTP_RETAILERS = {
    "bestbuy": check_bestbuy,
    "canadacomputers": check_canadacomputers,
}
BROWSER_RETAILERS = {
    "walmart": check_walmart,
    "amazon": check_amazon,
    "staples": check_staples,
}
RETAILERS = {**HTTP_RETAILERS, **BROWSER_RETAILERS}
# Stores whose search always shows the console, in stock or not (Amazon's
# sold-by-Amazon filter hides it when sold out, so it isn't in this list).
EXPECT_LISTING = {"bestbuy", "canadacomputers", "walmart", "staples"}


# --------------------------------------------------------------------------
# Alerts and state
# --------------------------------------------------------------------------

def notify(cfg: dict, title: str, message: str, click: str | None = None,
           priority: str = "urgent", tags: str = "video_game,rotating_light") -> None:
    headers = {
        # HTTP headers must be plain ASCII
        "Title": title.encode("ascii", "ignore").decode(),
        "Priority": priority,
        "Tags": tags,
    }
    if click:
        headers["Click"] = click
    url = f"{cfg['ntfy']['server'].rstrip('/')}/{cfg['ntfy']['topic']}"
    r = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=TIMEOUT)
    r.raise_for_status()


ALARM_SOUND = r"C:\Windows\Media\Alarm01.wav"
ALARM_MAX_SECONDS = 5 * 60  # the sound stops by itself after 5 min; the pop-up stays


def laptop_alarm(title: str, message: str, url: str = "") -> None:
    """Start the laptop alarm in its own process, so the stock check isn't held up
    while the pop-up waits for you. Never raises."""
    import subprocess
    try:
        python = Path(sys.executable)
        pythonw = python.with_name("pythonw.exe") if python.with_name("pythonw.exe").exists() else python
        args = [str(pythonw), str(Path(__file__).resolve()), "--alarm", title, message, url]
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        try:  # also leave the scheduled task's job, so ending the task can't kill the alarm
            subprocess.Popen(args, creationflags=flags | 0x01000000, close_fds=True)
        except OSError:
            subprocess.Popen(args, creationflags=flags, close_fds=True)
    except Exception as e:
        log.error("could not start the laptop alarm: %s", e)


def run_alarm(title: str, message: str, url: str) -> None:
    """Loop a loud sound and show an always-on-top pop-up until you answer it."""
    import ctypes
    import threading
    import webbrowser
    import winsound
    sound = ALARM_SOUND if Path(ALARM_SOUND).exists() else None
    if sound:
        winsound.PlaySound(sound, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
        threading.Timer(ALARM_MAX_SECONDS, lambda: winsound.PlaySound(None, 0)).start()
    # MB_YESNO | MB_ICONWARNING | MB_SYSTEMMODAL | MB_SETFOREGROUND | MB_TOPMOST
    flags = 0x4 | 0x30 | 0x1000 | 0x10000 | 0x40000
    text = f"{title}\n\n{message}\n\nOpen the product page now?"
    answer = ctypes.windll.user32.MessageBoxW(None, text, "PS5 stock alert", flags)
    winsound.PlaySound(None, 0)
    if answer == 6 and url:  # IDYES
        webbrowser.open(url)
    os._exit(0)  # don't wait for the sound timer


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"in_stock": {}, "failures": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _history_csv(event: str, ts: float, store: str, price, title: str, url: str) -> None:
    """Append one line to stock_history.csv (opens in Excel). Never raises."""
    import csv
    try:
        new = not HISTORY_CSV.exists()
        with HISTORY_CSV.open("a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time", "event", "store", "price", "title", "url"])
            w.writerow([time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)), event, store,
                        f"{price:.2f}" if price is not None else "", title, url])
    except Exception as e:
        log.error("could not write %s: %s", HISTORY_CSV.name, e)


def record_in_stock(state: dict, state_key: str, o: "Offer") -> None:
    """Start a history entry for an offer that just came in stock (once per restock)."""
    history = state.setdefault("history", [])
    if any(h["key"] == state_key and h.get("end") is None for h in history):
        return  # already recorded (e.g. the alert failed and is being retried)
    now = time.time()
    history.append({"key": state_key, "product": product_of(o.title), "store": o.retailer,
                    "title": o.title, "price": o.price, "url": o.url, "start": now, "end": None})
    del history[:-HISTORY_KEEP]
    _history_csv(f"{(product_of(o.title) or 'PS5').upper()} IN STOCK", now, o.retailer, o.price, o.title, o.url)


def record_sold_out(state: dict, state_key: str, o: "Offer") -> None:
    """Close the open history entry for an offer that is no longer available."""
    for h in reversed(state.get("history", [])):
        if h["key"] == state_key and h.get("end") is None:
            h["end"] = time.time()
            _history_csv(f"{(h.get('product') or 'PS5').upper()} SOLD OUT", h["end"],
                         o.retailer, o.price, o.title, o.url)
            return


def run_once(cfg: dict, dry_run: bool = False) -> int:
    state = load_state()
    state.setdefault("in_stock", {})
    state.setdefault("failures", {})
    state.setdefault("history_since", time.time())

    session = requests.Session()
    session.headers.update(HEADERS)
    threshold = cfg.get("failure_alert_after", 6)
    matches_in_stock = 0

    enabled = [k for k, on in cfg["retailers"].items() if on and k in RETAILERS]
    http_keys = [k for k in enabled if k in HTTP_RETAILERS]
    browser_keys = [k for k in enabled if k in BROWSER_RETAILERS]

    def process(key, fetch):
        nonlocal matches_in_stock
        try:
            offers = fetch()
            # These stores keep the console listed even when sold out, so finding
            # zero listings of the watched console means the page changed - not "sold out".
            if key in EXPECT_LISTING and not any(is_console_listing(o, cfg) for o in offers):
                raise RuntimeError("no PS5 console listing found at all - page format may have changed")
        except Exception as e:
            n = state["failures"].get(key, 0) + 1
            state["failures"][key] = n
            state.setdefault("last_check", {})[key] = {
                "time": time.time(), "ok": False, "error": str(e).splitlines()[0][:150]}
            log.warning("%s check failed (%d in a row): %s", key, n, e)
            if n == threshold and not dry_run:
                try:
                    notify(cfg, f"PS5 watcher: {key} check is failing",
                           f"The {key} check has failed {n} times in a row.\nLast error: {e}\n"
                           "Stock at this store is NOT being watched until it recovers.",
                           priority="default", tags="warning")
                except Exception as ne:
                    log.error("could not send failure alert: %s", ne)
            return

        if state["failures"].get(key, 0) >= threshold and not dry_run:
            try:
                notify(cfg, f"PS5 watcher: {key} check is working again",
                       f"The {key} check recovered.", priority="low", tags="white_check_mark")
            except Exception as ne:
                log.error("could not send recovery alert: %s", ne)
        state["failures"][key] = 0
        found = []  # matching consoles in stock right now, for --status

        for o in offers:
            state_key = f"{key}:{o.id}"
            product = product_of(o.title)
            if product not in watched(cfg):
                # Not watched (any more): forget it, so no "sold out" is logged for it.
                state["in_stock"].pop(state_key, None)
                for h in state.get("history", []):
                    if h["key"] == state_key and h.get("end") is None:
                        h["end"] = time.time()
                continue
            ok, reason = passes_filters(o, cfg)
            price = f"${o.price:,.2f}" if o.price is not None else "?"
            if dry_run and is_console_listing(o, cfg):
                mark = ("IN STOCK" if o.in_stock else "out") if ok else "skip"
                print(f"  [{o.retailer}] {mark:8} {price:>10}  {o.title[:80]}  ({reason}; {o.stock_note})")

            now_available = ok and o.in_stock
            was_available = state["in_stock"].get(state_key, False)
            if now_available:
                matches_in_stock += 1
                found.append({"product": product, "title": o.title, "price": o.price, "url": o.url,
                              "note": o.stock_note})
                if not was_available:
                    log.info("IN STOCK: %s %s %s %s %s", product, o.retailer, price, o.title, o.url)
                    if not dry_run:
                        record_in_stock(state, state_key, o)
                        if cfg.get("laptop_alarm", False):
                            laptop_alarm(f"{product.upper()} IN STOCK at {o.retailer} - {price}",
                                         f"{o.title}\n{o.stock_note}", o.url)
                        try:
                            notify(cfg, f"{product.upper()} IN STOCK at {o.retailer} - {price}",
                                   f"{product}: {o.title}\n{price} at {o.retailer}\n{o.stock_note}\n{o.url}",
                                   click=o.url)
                        except Exception as ne:
                            log.error("could not send stock alert: %s", ne)
                            continue  # leave state unchanged so we retry next run
            elif was_available:
                log.info("no longer available: %s %s", o.retailer, o.title)
                if not dry_run:
                    record_sold_out(state, state_key, o)
            if not dry_run:
                state["in_stock"][state_key] = now_available

        listings = {p: sum(is_console_listing(o, cfg) and product_of(o.title) == p for o in offers)
                    for p in watched(cfg)}
        state.setdefault("last_check", {})[key] = {
            "time": time.time(), "ok": True, "products": len(offers),
            "listings": listings, "in_stock": found}
        log.info("%s: %d products checked (%s)", key, len(offers),
                 ", ".join(f"{n} {p} listings" for p, n in listings.items()))

    for key in http_keys:
        process(key, lambda: HTTP_RETAILERS[key](session, queries_for(key, cfg)))

    # The browser opens a visible window, so it runs less often than the quick checks.
    every = cfg.get("browser_check_minutes", 20) * 60
    browser_due = dry_run or time.time() - state.get("last_browser_run", 0) >= every - 60
    if browser_keys and browser_due:
        if not dry_run:
            state["last_browser_run"] = time.time()
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="msedge", headless=False)
                try:
                    ctx = browser.new_context(locale="en-CA", viewport={"width": 1280, "height": 800})
                    page = ctx.new_page()
                    for key in browser_keys:
                        process(key, lambda: BROWSER_RETAILERS[key](page, queries_for(key, cfg)))
                finally:
                    browser.close()
        except Exception as e:
            log.error("could not run the browser: %s", e)
            def browser_failed():
                raise RuntimeError(f"browser failed: {e}")
            for key in browser_keys:
                process(key, browser_failed)

    if not dry_run:
        state["last_run"] = time.time()
        save_state(state)
    return matches_in_stock


# --------------------------------------------------------------------------
# Status screen  (python ps5_watch.py --status   or just:  ps5)
# --------------------------------------------------------------------------

TASK_NAME = "PS5 Stock Watch"
STORE_NAMES = {"bestbuy": "Best Buy", "canadacomputers": "Canada Computers",
               "staples": "Staples", "walmart": "Walmart", "amazon": "Amazon.ca"}
GREEN, RED, YELLOW, BOLD, DIM, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[2m", "\033[0m"


def _task_info() -> dict | None:
    import subprocess
    ps = (f"$t = Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue; "
          f"if ($t) {{ $i = Get-ScheduledTaskInfo -TaskName '{TASK_NAME}'; "
          "@{State=[string]$t.State; Next=$i.NextRunTime.ToString('o'); Result=$i.LastTaskResult} | ConvertTo-Json }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return json.loads(out) if out else None
    except Exception:
        return None


def _ago(ts: float | None) -> str:
    if not ts:
        return "never"
    mins = int((time.time() - ts) // 60)
    when = time.strftime("%I:%M %p", time.localtime(ts)).lstrip("0")
    if mins < 1:
        return f"{when} (just now)"
    if mins < 120:
        return f"{when} ({mins} min ago)"
    return f"{time.strftime('%b %d', time.localtime(ts))} {when} ({mins // 60} h ago)"


def show_status(cfg: dict) -> None:
    os.system("")  # turns on colours in the Windows console
    state = load_state()
    task = _task_info()
    last_run = state.get("last_run")
    stale_after = 15 * 60  # task runs every 5 min; allow a couple of misses

    print(f"\n{BOLD}PS5 stock watcher ({' + '.join(watched(cfg))}){RESET}   {DIM}{time.strftime('%a %b %d, %I:%M %p')}{RESET}\n")

    if task is None:
        verdict = f"{RED}NOT RUNNING - the scheduled task is not installed (run install_task.ps1){RESET}"
    elif task["State"] == "Disabled":
        verdict = f"{RED}NOT RUNNING - the scheduled task is disabled{RESET}"
    elif not last_run:
        verdict = f"{YELLOW}STARTING - waiting for the first check to finish{RESET}"
    elif time.time() - last_run > stale_after:
        verdict = (f"{YELLOW}PAUSED - no check since {_ago(last_run)}. Usually means the PC was "
                   f"asleep; checks resume by themselves within 5 min of waking{RESET}")
    elif task["State"] == "Running":
        verdict = f"{GREEN}RUNNING - checking the stores right now{RESET}"
    else:
        verdict = f"{GREEN}RUNNING{RESET}"
    print(f"  Status:      {verdict}")
    print(f"  Last check:  {_ago(last_run)}")
    if task and task.get("Next"):
        try:
            from datetime import datetime
            nxt = datetime.fromisoformat(task["Next"]).strftime("%I:%M %p").lstrip("0")
            print(f"  Next check:  {nxt}")
        except ValueError:
            pass
    limits = ", ".join(f"{p} under ${m:,}" for p, m in cfg["filters"]["max_price"].items())
    print(f"  Alerts to:   ntfy topic {cfg['ntfy']['topic']}   ({limits})")

    for product in watched(cfg):
        _status_table(cfg, state, product)
    print()


# Stores that don't sell a product at all (shown instead of "not available").
NOT_SOLD = {}  # e.g. {("store", "PS5 Pro"): "Store doesn't sell the PS5 Pro"}


def _status_table(cfg: dict, state: dict, product: str) -> None:
    max_price = cfg["filters"]["max_price"][product]
    browser_every = cfg.get("browser_check_minutes", 20)
    checks = state.get("last_check", {})
    in_stock = []
    print(f"\n  {BOLD}=== {product} (under ${max_price:,}) ==={RESET}")
    print(f"  {BOLD}{'Store':<18}{'Last checked':<26}Result{RESET}")
    for key, enabled in cfg["retailers"].items():
        name = STORE_NAMES.get(key, key)
        if not enabled:
            print(f"  {DIM}{name:<18}{'-':<26}turned off in config.yaml{RESET}")
            continue
        c = checks.get(key)
        if not c:
            print(f"  {name:<18}{'not yet':<26}{DIM}waiting for first check{RESET}")
            continue
        limit = (browser_every * 2 + 10 if key in BROWSER_RETAILERS else 15) * 60
        when = _ago(c["time"])
        if time.time() - c["time"] > limit:
            when = f"{YELLOW}{when}{RESET}" + " " * max(0, 26 - len(when))
        else:
            when = f"{when:<26}"
        mine = [s for s in c.get("in_stock", []) if s.get("product", "PS5 Digital") == product]
        if not c["ok"]:
            fails = state.get("failures", {}).get(key, 0)
            result = f"{RED}FAILED{RESET} ({fails} in a row): {c['error'][:60]}"
        elif mine:
            result = f"{GREEN}{BOLD}IN STOCK!{RESET}"
            in_stock += [(name, s) for s in mine]
        elif (key, product) in NOT_SOLD:
            result = f"{DIM}{NOT_SOLD[(key, product)]}{RESET}"
        elif key == "amazon":
            result = f"Not available {DIM}(Amazon.ca itself isn't selling it right now){RESET}"
        else:
            n = c.get("listings", {}).get(product, 0)
            pages = f"{n} {product} product page" + ("s, all" if n != 1 else ",")
            result = f"Not available {DIM}(found {pages} sold out or over ${max_price:,}){RESET}"
        print(f"  {name:<18}{when}{result}")

    if not in_stock:
        print(f"\n  No {product} to buy yet. You'll get a phone alert the moment that changes.")
    else:
        print(f"\n  {GREEN}{BOLD}{product} AVAILABLE NOW:{RESET}")
        for name, s in in_stock:
            price = f"${s['price']:,.2f}" if s.get("price") is not None else "?"
            print(f"    {name}: {price}  {s['title']}")
            if s.get("note"):
                print(f"      {s['note']}")
            print(f"      {s['url']}")
    print(f"  Last available {product}:  {last_available(state, product)}")


def _when(ts: float) -> str:
    return time.strftime("%a %b %d, %I:%M %p", time.localtime(ts)).replace(" 0", " ")


def last_available(state: dict, product: str = "PS5 Digital") -> str:
    history = [h for h in state.get("history", []) if h.get("product", "PS5 Digital") == product]
    if not history:
        since = state.get("history_since")
        return f"{DIM}none seen yet{' (tracking since ' + _when(since) + ')' if since else ''}{RESET}"
    h = max(history, key=lambda h: h["start"])
    price = f"${h['price']:,.2f}" if h.get("price") is not None else "?"
    if h.get("end") is None:
        ended = f"{GREEN}still in stock{RESET}"
    else:
        ended = f"sold out by {time.strftime('%I:%M %p', time.localtime(h['end'])).lstrip('0')}"
    return f"{BOLD}{STORE_NAMES.get(h['key'].split(':')[0], h['store'])}{RESET} - {price} - {_when(h['start'])} ({ended})"


def setup_logging(verbose: bool) -> None:
    log.setLevel(logging.INFO)
    fh = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)
    if verbose and sys.stdout:
        log.addHandler(logging.StreamHandler(sys.stdout))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print results, send no alerts, don't save state")
    ap.add_argument("--test-alert", action="store_true", help="send a test notification and exit")
    ap.add_argument("--status", action="store_true", help="show whether the watcher is running and what it found")
    ap.add_argument("--live", action="store_true", help="with --status: refresh every 30 seconds (Ctrl+C to quit)")
    ap.add_argument("--alarm", nargs=3, metavar=("TITLE", "MESSAGE", "URL"), help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.alarm:  # started by laptop_alarm() in its own process
        run_alarm(*args.alarm)
        return

    if not CONFIG_FILE.exists():
        sys.exit(f"No {CONFIG_FILE.name} found. Copy config.example.yaml to {CONFIG_FILE.name} "
                 "and set your own ntfy topic in it.")
    cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
    if args.status:
        try:
            while True:
                if args.live:
                    print("\033[2J\033[H", end="")  # clear screen (works in PowerShell and bash)
                show_status(cfg)
                if not args.live:
                    return
                print(f"  {DIM}Refreshing every 30 s - press Ctrl+C to stop{RESET}")
                time.sleep(30)
        except KeyboardInterrupt:
            return
    setup_logging(verbose=args.dry_run or args.test_alert)

    if args.test_alert:
        notify(cfg, "PS5 watcher test", "If you can read this, alerts are working.",
               priority="default", tags="white_check_mark")
        print("Test alert sent to topic:", cfg["ntfy"]["topic"])
        if cfg.get("laptop_alarm", False):
            laptop_alarm("PS5 watcher test", "If you hear the alarm and see this, laptop alerts work.")
            print("Laptop alarm started: click Yes or No on the pop-up to stop it.")
        return

    start = time.time()
    n = run_once(cfg, dry_run=args.dry_run)
    log.info("check done in %.1fs, %d matching offer(s) in stock", time.time() - start, n)


if __name__ == "__main__":
    main()
