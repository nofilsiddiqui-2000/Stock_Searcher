"""Run with:  python -m pytest test_matcher.py   (or just: python test_matcher.py)
Titles below are real listings seen on Best Buy / Canada Computers."""

from ps5_watch import Offer, is_ps5_digital, passes_filters, product_of

SHOULD_MATCH = [
    "PlayStation 5 Slim Digital Edition 825GB Console",
    "SONY PlayStation®5 Slim Console - Digital Edition",
    "PlayStation 5 Digital Edition 825GB Console Marvel’s Wolverine Battle Yellow Limited Edition Bundle",
    "PlayStation 5 Digital Edition – Fortnite Cobalt Star Bundle",
    "PS5 Digital Edition Console",
    "PlayStation 5 Digital Edition Bundle with DualSense Charging Station",
    "PS5 Slim Digital Edition Console + Carrying Case Bundle",
    "PlayStation 5 Digital Edition Console + 12-Month PlayStation Plus Membership Bundle",
    "PS5 Digital Edition Console Bundle with Charging Dock and Console Cover",
    "PlayStation5 Digital Edition Slim + $20 PSN Gift Card",
]

# Accessories pass the title rules on purpose; the min_price filter must stop them.
CHEAP_ACCESSORIES = [
    ("PlayStation 5 Digital Edition Charging Station", 39.99),
    ("Carrying Case PS5 Slim Digital Edition", 49.99),
    ("PlayStation 5 Digital Edition Console Cover - Starlight Blue", 69.99),
    ("3-in-1 Vertical Stand with 2 Cooling Fan and Charging Station Dock for PS5 Console and PlayStation 5 Digital Edition", 45.99),
    ("PS5 Stand with 3-Speed Fan, RGB Light, Controller Charging Dock, Digital Edition", 39.99),
    ("RGB LED Light Strip for PS5 Disc & Digital Edition Consoles", 19.99),
    ("PlayStation 5 Slim Edition Console Cover - Cobalt Blue", 69.99),   # reads like a Disc
    ("Multifunctional Cooling Stand for PS5 Pro", 49.99),                # reads like a Pro
]

SHOULD_NOT_MATCH = [
    "SONY PlayStation®5 Pro Digital Edition",
    "PlayStation 5 Pro Console",
    "PlayStation 5 Slim 1TB Console",
    "PlayStation 5 Disc Edition Console (slim)",
    "Disc Drive For PlayStation 5 Digital Edition Console / PlayStation 5 Pro Console - White",
    "PS5 Disc Drive Add-On for PS5 Digital Edition Slim CFI-2000 and PS5 Pro 4K Ultra HD Blu-ray",
    "PS5 Cooling Fan with LED Light, PS5 Accessories Cooler Fan for Playstation 5 Digital & Disc Edition Console",
    "Horizontal Stand for PS5 Disc & Digital Editions, No Screws Removable Stable PS5 Base Stand Anti-Slip",
    "PlayStation 5 Digital Edition Call of Duty: Black Ops 6 Bundle (Slim Model CFI-2000) – (Open Box)",
    "Certified Refurbished - PlayStation 5 Slim Digital Edition Console",
    "Sony Disc Drive for PlayStation 5 Digital Edition Console",           # Staples
    "Western Digital SN850P NVMe SSD for PS5 consoles - 2TB - Black",      # Staples
]

DISC_TITLES = [  # the regular PS5 with a disc drive; stores rarely say "disc"
    "PlayStation 5 Slim 1TB Console",                    # Best Buy
    "Sony PlayStation 5 Slim Console",                   # Staples
    "SONY PlayStation®5 Slim Console",
    "PlayStation®5 Console (slim)",
    "PlayStation 5 Disc Edition Console (slim)",
    "PS5 Slim Standard Edition",
    "PlayStation 5 Console – Call of Duty Black Ops 6 Bundle",
    "PS5 Slim Console Bundle with Digital Game Code",
    "PlayStation 5 Console with Disc Drive",
    "PlayStation 5 Digital Edition + Disc Drive Bundle",       # a disc console in effect
    "PS5 Slim Digital Edition Console with PS5 Disc Drive",
    "PlayStation®5 Disc Console Slim – 1TB",                                    # Walmart
    "PlayStation®5 Console – Ghost of Yōtei Gold  Limited Edition Bundle",     # Walmart
    "PlayStation®5 Console 1TB – Fortnite Flowering Chaos Bundle",             # Walmart
    "PlayStation 5 Slim Console + PlayStation 5 DualSense Wireless Controller Galactic Purple",
]
NOT_DISC = [  # mention the PS5 (and often "console"), but are not a new disc console
    "PlayStation 5 Slim Digital Edition 825GB Console",
    "SONY PlayStation®5 Slim Console - Digital Edition",
    "PlayStation 5 Pro Console",
    "Sony Disc Drive for PlayStation 5 Digital Edition Console",
    "Western Digital SN850P NVMe SSD for PS5 consoles - 2TB - Black",
    "WD_BLACK 2TB SN850P NVMe M.2 SSD Officially Licensed Storage Expansion for PS5 Consoles, up to 7300MB/s",
    "PlayStation Portal Remote Player (PS5) - White",
    "Thrustmaster T598 Direct Axial Drive Racing Wheel & Pedal Set for PS5/PS4/PC",
    "Certified Refurbished - PlayStation 5 Slim 1TB Console",
    "Open Box - PlayStation 5 Ghost of Yōtei Black Limited Edition Console only",
    "God Of War Ragnarok (Replen) for Playstation 5 [Disc]",
    "Spider-Man 2 Collector's Edition (PS5) - Open Box (Console Not Included)",
    "Cooling Fan Stand for PS5 Console",
    "PS5 Cooling Fan with LED Light, PS5 Accessories Cooler Fan for Playstation 5 Digital & Disc Edition Console",
    "Bigly Brothers PS5 Gaming Bundle Pro – Wireless Headset, Wireless Controller",
    "Sony PlayStation 5 DualSense Wireless Controller - White",
    "PlayStation 5 Media Remote",
    "Disc Drive For PlayStation 5 Digital Edition Console / PlayStation 5 Pro Console - White",
    "PS5 Disc Drive Add-On for PS5 Digital Edition Slim CFI-2000 and PS5 Pro 4K Ultra HD Blu-ray",
    "Disc Drive - PlayStation 5 Digital Edition Console",
    "PlayStation®5 Pro Console PLUS Disc Drive For PS5® Digital Edition Consoles, Bundle",
    "Sony - PlayStation 5 (PS5) Disc Console Slim - White (Refurbished)",       # Walmart
    "Sony 3006634 PlayStation 5 Console - White (Refurbished)",                 # Walmart
    "PlayStation®5 Digital Edition – 825GB",                                    # Walmart (Digital)
]

CFG = {"filters": {"max_price": {"PS5 Digital": 850, "PS5 Disc": 950, "PS5 Pro": 1200}, "min_price": 300,
                   "first_party_only": True}}

PRO_TITLES = [  # real listings seen at Best Buy / Canada Computers / Walmart
    "PlayStation 5 Pro Console",
    "SONY PlayStation®5 Pro Digital Edition",
    "PlayStation®5 Pro Console PLUS Disc Drive For PS5® Digital Edition Consoles, Bundle",
    "PlayStation 5 Pro Digital Edition Fortnite Cobalt Star Bundle",
    "PS5 Pro Console - 2TB",
]
NOT_PRO = [  # have "Pro" and "PS5" but are not the console
    "Razer Raiju V3 Pro Wireless Gaming Controller - PS5/PC - Black",
    "Logitech G PRO X Gaming Headset with Blue VO!CE - PC, Xbox One, PS5, PS4, Nintendo Switch - Black",
    "Certified Refurbished - PlayStation 5 Pro Console",
    "PlayStation 5 Pro Console (Open Box)",
]


def test_products_never_mixed():
    for t in SHOULD_MATCH:
        assert product_of(t) == "PS5 Digital", t
    for t in PRO_TITLES:
        assert product_of(t) == "PS5 Pro", t
    for t in NOT_PRO:
        assert product_of(t) is None, t
    # each console has its own price limit
    assert passes_filters(offer("PlayStation 5 Pro Console", 1099.99), CFG)[0]
    assert not passes_filters(offer("PlayStation 5 Pro Console", 1200.00), CFG)[0]
    assert not passes_filters(offer(SHOULD_MATCH[0], 1099.99), CFG)[0]   # Digital over $850
    assert not passes_filters(offer("Vertical Stand For PlayStation 5 / PlayStation 5 Pro Console", 39.99), CFG)[0]


def test_disc_console():
    for t in DISC_TITLES:
        assert product_of(t) == "PS5 Disc", t
    for t in NOT_DISC:
        assert product_of(t) != "PS5 Disc", t
    cfg = {"filters": {"max_price": {"PS5 Digital": 850, "PS5 Disc": 950, "PS5 Pro": 1250},
                       "min_price": 300, "first_party_only": True}}
    assert passes_filters(offer(DISC_TITLES[0], 819.99), cfg)[0]
    assert not passes_filters(offer(DISC_TITLES[0], 999.99), cfg)[0]          # over $950
    assert not passes_filters(offer(DISC_TITLES[0], 819.99, False), cfg)[0]   # reseller
    assert passes_filters(offer(SHOULD_MATCH[0], 749.99), cfg)[0]             # Digital 825GB
    assert passes_filters(offer(SHOULD_MATCH[1], 749.99), cfg)[0]             # Digital (1TB slim)


def offer(title, price, first_party=True):
    return Offer("Test", "1", title, price, "http://x", True, first_party)


def test_titles():
    for t in SHOULD_MATCH:
        assert is_ps5_digital(t), f"should match: {t}"
    for t in SHOULD_NOT_MATCH:
        assert not is_ps5_digital(t), f"should NOT match: {t}"


def test_price_and_seller():
    t = SHOULD_MATCH[0]
    assert passes_filters(offer(t, 749.99), CFG)[0]
    assert passes_filters(offer(t, 819.99), CFG)[0]       # Wolverine bundle price: now allowed
    assert passes_filters(offer(t, 849.99), CFG)[0]
    assert not passes_filters(offer(t, 850.00), CFG)[0]   # must be UNDER 850
    assert not passes_filters(offer(t, 1499.99), CFG)[0]  # scalper price
    assert not passes_filters(offer(t, 749.99, first_party=False), CFG)[0]
    assert passes_filters(offer(t, None), CFG)[0]                    # price unreadable: alert anyway
    assert not passes_filters(offer(t, None, first_party=False), CFG)[0]
    for title, price in CHEAP_ACCESSORIES:
        assert not passes_filters(offer(title, price), CFG)[0], title


def test_alert_only_on_restock(tmp_dir=None):
    import tempfile
    from pathlib import Path
    import ps5_watch

    stock = {"value": False}
    pro_stock = {"value": False}
    sent = []
    ps5_watch.RETAILERS["fake"] = ps5_watch.HTTP_RETAILERS["fake"] = lambda s, q=None: [Offer("Fake", "1", SHOULD_MATCH[0], 749.99, "http://x", stock["value"]),
                                                                                Offer("Fake", "2", PRO_TITLES[0], 1099.99, "http://y", pro_stock["value"])]
    orig = ps5_watch.notify, ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV
    fail_notify = {"value": False}

    def fake_notify(cfg, title, *a, **k):
        if fail_notify["value"]:
            raise RuntimeError("network down")
        sent.append(title)

    tmp = Path(tempfile.mkdtemp())
    ps5_watch.notify = fake_notify
    ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV = tmp / "state.json", tmp / "history.csv"
    cfg = {**CFG, "retailers": {"fake": True}, "failure_alert_minutes": 60}
    history = lambda: ps5_watch.load_state().get("history", [])
    try:
        ps5_watch.run_once(cfg); assert sent == [] and history() == []   # out of stock: nothing
        assert "none seen yet" in ps5_watch.last_available(ps5_watch.load_state())
        stock["value"] = True
        fail_notify["value"] = True
        ps5_watch.run_once(cfg); assert sent == []          # alert failed...
        assert len(history()) == 1                          # ...but the restock is still recorded
        fail_notify["value"] = False
        ps5_watch.run_once(cfg); assert len(sent) == 1      # alert retried and sent
        ps5_watch.run_once(cfg); assert len(sent) == 1      # still in stock: no repeat
        h = history(); assert len(h) == 1 and h[0]["end"] is None   # no duplicate entry
        assert "still in stock" in ps5_watch.last_available(ps5_watch.load_state())
        stock["value"] = False
        ps5_watch.run_once(cfg)
        h = history(); assert h[0]["end"] is not None       # sold-out time recorded
        assert "sold out by" in ps5_watch.last_available(ps5_watch.load_state())
        stock["value"] = True
        ps5_watch.run_once(cfg); assert len(sent) == 2      # sold out then back: alert again
        assert len(history()) == 2
        assert all(t.startswith("PS5 DIGITAL IN STOCK") for t in sent), sent
        pro_stock["value"] = True                           # Pro restock: its own, separate alert
        ps5_watch.run_once(cfg); assert len(sent) == 3 and sent[-1].startswith("PS5 PRO IN STOCK"), sent
        st = ps5_watch.load_state()
        assert "Fake" in ps5_watch.last_available(st, "PS5 Pro")
        assert [h["product"] for h in st["history"]] == ["PS5 Digital", "PS5 Digital", "PS5 Pro"]
        rows = ps5_watch.HISTORY_CSV.read_text(encoding="utf-8-sig").splitlines()
        assert [r.split(",")[1] for r in rows] == ["event", "PS5 DIGITAL IN STOCK", "PS5 DIGITAL SOLD OUT",
                                                       "PS5 DIGITAL IN STOCK", "PS5 PRO IN STOCK"], rows
    finally:
        ps5_watch.notify, ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV = orig
        del ps5_watch.RETAILERS["fake"], ps5_watch.HTTP_RETAILERS["fake"]


PRO_ONLY = {"filters": {"max_price": {"PS5 Pro": 1200}, "min_price": 300, "first_party_only": True}}


def test_pro_only():
    """config.yaml watching only the PS5 Pro: a Digital in stock must never alert."""
    import tempfile
    from pathlib import Path
    import ps5_watch

    assert ps5_watch.watched(PRO_ONLY) == ["PS5 Pro"]
    assert not passes_filters(offer(SHOULD_MATCH[0], 749.99), PRO_ONLY)[0]
    assert passes_filters(offer("PlayStation 5 Pro Console", 1099.99), PRO_ONLY)[0]
    # only Pro searches are run
    assert ps5_watch.queries_for("bestbuy", PRO_ONLY) == ps5_watch.SEARCHES["bestbuy"]["PS5 Pro"]
    for t in ("PS5Pro Console", "PS 5 Pro Console", "PlayStation 5 - Pro Console", "PlayStation 5 Pro Console - 2TB",
              "Sony PlayStation 5 Pro Console","PlayStation®5 Pro 2TB"):
        assert product_of(t) == "PS5 Pro", t

    pro = {"value": False}
    seen_queries, sent = [], []

    def fake(s, q=None):
        seen_queries.append(q)
        return [Offer("Fake", "1", SHOULD_MATCH[0], 749.99, "http://x", True),        # Digital, in stock
                Offer("Fake", "2", PRO_TITLES[0], 1099.99, "http://y", pro["value"])]

    tmp = Path(tempfile.mkdtemp())
    orig = ps5_watch.notify, ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV
    ps5_watch.notify = lambda cfg, title, *a, **k: sent.append(title)
    ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV = tmp / "state.json", tmp / "history.csv"
    ps5_watch.RETAILERS["fake"] = ps5_watch.HTTP_RETAILERS["fake"] = fake
    cfg = {**PRO_ONLY, "retailers": {"fake": True}}
    try:
        ps5_watch.save_state({"in_stock": {"fake:1": True}, "failures": {}})   # Digital was in stock before
        ps5_watch.run_once(cfg)
        st = ps5_watch.load_state()
        assert sent == [] and "fake:1" not in st["in_stock"]       # no alert, no "sold out" noise
        assert st["last_check"]["fake"]["listings"] == {"PS5 Pro": 1}
        pro["value"] = True
        ps5_watch.run_once(cfg)
        assert len(sent) == 1 and sent[0].startswith("PS5 PRO IN STOCK"), sent
    finally:
        ps5_watch.notify, ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV = orig
        del ps5_watch.RETAILERS["fake"], ps5_watch.HTTP_RETAILERS["fake"]


def test_bestbuy_online_only():
    """Only online stock counts: on the shelf in a store but sold out online is NOT in stock."""
    import ps5_watch

    class Resp:
        def __init__(self, data): self.data = data
        def raise_for_status(self): pass
        def json(self): return self.data

    def avail(sku, ship_ok, stores):
        return {"sku": sku, "sellerId": "bbyca",
                "shipping": {"purchasable": ship_ok, "status": "InStock" if ship_ok else "SoldOutOnline"},
                "pickup": {"purchasable": bool(stores), "status": "InStock" if stores else "OutOfStock",
                           "locations": [{"name": n, "hasInventory": q > 0, "quantityOnHand": q} for n, q in stores]}}

    class Session:
        def get(self, url, params=None, **k):
            if "search" in url:
                return Resp({"products": [{"sku": s, "name": SHOULD_MATCH[0], "salePrice": 749.99,
                                           "productUrl": "/p/" + s} for s in ("1", "2", "3")]})
            assert "locations" not in params, "no pickup stores are asked for"
            return Resp({"availabilities": [avail("1", False, [("Montreal Eaton Centre", 2)]),
                                            avail("2", False, []),
                                            avail("3", True, [])]})

    got = {o.id: o for o in ps5_watch.check_bestbuy(Session())}
    assert not got["1"].in_stock                        # in a store only (the 3 PM / 6 PM Pro alerts)
    assert not got["2"].in_stock                        # sold out everywhere
    assert got["3"].in_stock and got["3"].stock_note == "online: InStock"   # online


def test_canadacomputers_online_only():
    """Sold out online but in stock at a store: NOT in stock, and no product page is opened."""
    import ps5_watch

    def card(n, online):
        return (f'<div class="js-product" id="product_card_{n}"><h2 class="product-title">'
                f'<a href="https://cc/{n}.html">SONY PlayStation®5 Slim Console - Digital Edition</a></h2>'
                f'<div class="product-description" data-final_price="749.99"></div>'
                f'<div class="available-tag"><span>{online}</span><span>In-Store - Available</span></div></div>')

    asked = []

    class Resp:
        text = card(1, "Online - Sold Out") + card(2, "Online - Available to Ship")
        def raise_for_status(self): pass

    class Session:
        def get(self, url, **k):
            asked.append(url); return Resp()

    got = {o.id: o for o in ps5_watch.check_canadacomputers(Session())}
    assert not got["1"].in_stock and got["2"].in_stock
    assert asked == [ps5_watch.CC_PLAYSTATION_PAGE]          # one request, no store lookups


def test_failing_store_slows_down():
    """A blocked store is checked less often, you're warned once after an hour,
    and it goes back to normal on its first success."""
    import tempfile
    from pathlib import Path
    import ps5_watch

    calls, sent, blocked = [], [], {"value": True}

    def fake(s, q=None):
        calls.append(1)
        if blocked["value"]:
            raise RuntimeError("403 Client Error: Forbidden")
        return [Offer("Fake", "1", PRO_TITLES[0], 1099.99, "http://y", False)]

    tmp = Path(tempfile.mkdtemp())
    orig = ps5_watch.notify, ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV
    ps5_watch.notify = lambda cfg, title, *a, **k: sent.append(title)
    ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV = tmp / "state.json", tmp / "history.csv"
    ps5_watch.RETAILERS["fake"] = ps5_watch.HTTP_RETAILERS["fake"] = fake
    cfg = {**PRO_ONLY, "retailers": {"fake": True}, "failure_alert_minutes": 60}

    def rewind(minutes):  # pretend the last check / first failure happened earlier
        st = ps5_watch.load_state()
        st["last_check"]["fake"]["time"] -= minutes * 60
        if "fake" in st.get("failing", {}):
            st["failing"]["fake"]["since"] -= minutes * 60
        ps5_watch.save_state(st)

    try:
        for _ in range(3):
            ps5_watch.run_once(cfg)
        assert len(calls) == 3                               # first 3 failures: normal speed
        ps5_watch.run_once(cfg); assert len(calls) == 3      # now slowed down: skipped
        assert ps5_watch.backoff_until(ps5_watch.load_state(), "fake")
        rewind(15); ps5_watch.run_once(cfg); assert len(calls) == 4   # tried again after 15 min
        ps5_watch.run_once(cfg); assert len(calls) == 4
        rewind(15); ps5_watch.run_once(cfg); assert len(calls) == 4   # next wait is 30 min
        rewind(15); ps5_watch.run_once(cfg); assert len(calls) == 5
        assert sent == []                                    # failing for under an hour: no warning yet
        st = ps5_watch.load_state(); st["failing"]["fake"]["since"] -= 3600; ps5_watch.save_state(st)
        ps5_watch.run_once(cfg); assert len(calls) == 5      # an hour in, store not due for a retry...
        assert sent == ["PS5 watcher: fake check is failing"], sent   # ...but the warning goes out anyway
        rewind(60); ps5_watch.run_once(cfg); assert len(calls) == 6
        rewind(60); ps5_watch.run_once(cfg); assert len(calls) == 7   # then hourly
        assert len(sent) == 1                                # no repeat warning
        blocked["value"] = False
        rewind(60); ps5_watch.run_once(cfg); assert len(calls) == 8
        assert sent[-1] == "PS5 watcher: fake check is working again"
        st = ps5_watch.load_state()
        assert st["failures"]["fake"] == 0 and not ps5_watch.backoff_until(st, "fake")
        ps5_watch.run_once(cfg); assert len(calls) == 9      # back to every run
    finally:
        ps5_watch.notify, ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV = orig
        del ps5_watch.RETAILERS["fake"], ps5_watch.HTTP_RETAILERS["fake"]


def test_canadacomputers_backup_page():
    """Category page blocked: the site search is used instead."""
    import requests
    import ps5_watch

    card = ('<div class="js-product" id="product_card_263621"><h2 class="product-title">'
            '<a href="https://cc/pro.html">SONY PlayStation 5 Pro Digital Edition</a></h2>'
            '<div class="product-description" data-final_price="1099.99"></div>'
            '<div class="available-tag"><span>Online - Available to Ship</span></div></div>')
    asked = []

    class Resp:
        def __init__(self, code, text=""): self.code, self.text = code, text
        def raise_for_status(self):
            if self.code != 200:
                raise requests.HTTPError(f"{self.code} Client Error: Forbidden")

    class Session:
        def __init__(self, search_ok): self.search_ok = search_ok
        def get(self, url, params=None, **k):
            asked.append((url, params))
            if url == ps5_watch.CC_PLAYSTATION_PAGE:
                return Resp(403)
            return Resp(200, card) if self.search_ok else Resp(403)

    offers = ps5_watch.check_canadacomputers(Session(True), ("PS5 Pro",))
    assert [o.title for o in offers] == ["SONY PlayStation 5 Pro Digital Edition"] and offers[0].in_stock
    assert asked[1][1] == {"s": "ps5 pro"}                   # searched for the watched console only
    try:
        ps5_watch.check_canadacomputers(Session(False), ("PS5 Pro",))
        assert False, "should fail when both pages are blocked"
    except RuntimeError as e:
        assert "category page" in str(e) and "search" in str(e)


def test_vanished_listing_alerts_again():
    """In stock, then gone from the results (Amazon hides sold-out items), then back:
    the comeback must alert again."""
    import tempfile
    from pathlib import Path
    import ps5_watch

    listed, sent = {"value": True}, []

    def fake(s, q=None):
        return [Offer("Fake", "9", PRO_TITLES[0], 1099.99, "http://y", True)] if listed["value"] else []

    tmp = Path(tempfile.mkdtemp())
    orig = ps5_watch.notify, ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV
    ps5_watch.notify = lambda cfg, title, *a, **k: sent.append(title)
    ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV = tmp / "state.json", tmp / "history.csv"
    ps5_watch.RETAILERS["fake"] = ps5_watch.HTTP_RETAILERS["fake"] = fake
    cfg = {**PRO_ONLY, "retailers": {"fake": True}}
    try:
        ps5_watch.run_once(cfg); assert len(sent) == 1
        listed["value"] = False
        ps5_watch.run_once(cfg)
        st = ps5_watch.load_state()
        assert st["in_stock"]["fake:9"] is False and st["history"][-1]["end"]   # counted as sold out
        listed["value"] = True
        ps5_watch.run_once(cfg); assert len(sent) == 2, sent                    # back: alerted again
    finally:
        ps5_watch.notify, ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV = orig
        del ps5_watch.RETAILERS["fake"], ps5_watch.HTTP_RETAILERS["fake"]


def test_cheapest_in_stock_price():
    """The status screen gets the cheapest in-stock price (resellers and over-limit too),
    without any alert for those."""
    import tempfile
    from pathlib import Path
    import ps5_watch

    sent = []

    def fake(s, q=None):
        return [Offer("Fake", "1", PRO_TITLES[0], 1099.99, "http://a", False),          # sold out
                Offer("Fake", "2", PRO_TITLES[0], 1599.99, "http://b", True, False),    # reseller
                Offer("Fake", "3", PRO_TITLES[0], 1399.99, "http://c", True, False),    # reseller
                Offer("Fake", "4", PRO_TITLES[0], 49.99, "http://d", True)]             # accessory

    tmp = Path(tempfile.mkdtemp())
    orig = ps5_watch.notify, ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV
    ps5_watch.notify = lambda cfg, title, *a, **k: sent.append(title)
    ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV = tmp / "state.json", tmp / "history.csv"
    ps5_watch.RETAILERS["fake"] = ps5_watch.HTTP_RETAILERS["fake"] = fake
    cfg = {**PRO_ONLY, "retailers": {"fake": True}}
    try:
        ps5_watch.run_once(cfg)
        assert not sent, sent
        low = ps5_watch.load_state()["last_check"]["fake"]["cheapest"]
        assert low == {"PS5 Pro": {"price": 1399.99, "reseller": True}}, low
    finally:
        ps5_watch.notify, ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV = orig
        del ps5_watch.RETAILERS["fake"], ps5_watch.HTTP_RETAILERS["fake"]


def test_staples_pages_in_turns():
    """Staples checks one page per visit. A console in stock on one page must not be
    counted as sold out (and re-alerted) because the next visit checked another page."""
    import tempfile
    from pathlib import Path
    import ps5_watch

    sent, turn = [], {"page": "digital"}
    pages = {"digital": Offer("Staples", "3140351", "Sony PlayStation 5 Digital Edition Console", 749.99, "http://d", True),
             "disc": Offer("Staples", "3140352", "Sony PlayStation 5 Slim Console", 819.99, "http://s", False)}

    def fake(s, q=None):
        return [pages[turn["page"]]]

    tmp = Path(tempfile.mkdtemp())
    orig = (ps5_watch.notify, ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV,
            ps5_watch.BROWSER_RETAILERS.pop("staples"))
    ps5_watch.notify = lambda cfg, title, *a, **k: sent.append(title)
    ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV = tmp / "state.json", tmp / "history.csv"
    ps5_watch.HTTP_RETAILERS["staples"] = fake
    cfg = {**PRO_ONLY, "filters": {**PRO_ONLY["filters"],
                                    "max_price": {"PS5 Digital": 850, "PS5 Disc": 950, "PS5 Pro": 1250}},
           "retailers": {"staples": True}}
    try:
        ps5_watch.run_once(cfg); assert len(sent) == 1, sent          # Digital in stock: alert
        turn["page"] = "disc"
        ps5_watch.run_once(cfg)
        st = ps5_watch.load_state()
        assert st["in_stock"]["staples:3140351"] is True              # not "vanished"
        c = st["last_check"]["staples"]
        assert c["listings"] == {"PS5 Digital": 1, "PS5 Disc": 1, "PS5 Pro": 0}, c["listings"]
        assert [s["product"] for s in c["in_stock"]] == ["PS5 Digital"]  # kept for --status
        assert set(c["checked"]) == {"PS5 Digital", "PS5 Disc"}
        turn["page"] = "digital"
        ps5_watch.run_once(cfg); assert len(sent) == 1, sent          # still in stock: no repeat
    finally:
        ps5_watch.notify, ps5_watch.STATE_FILE, ps5_watch.HISTORY_CSV, ps5_watch.BROWSER_RETAILERS["staples"] = orig
        del ps5_watch.HTTP_RETAILERS["staples"]


def test_crash_is_reported():
    """A whole check crashing warns the phone (at most hourly) and is cleared on success."""
    import tempfile
    from pathlib import Path
    import ps5_watch

    sent = []
    tmp = Path(tempfile.mkdtemp())
    orig = ps5_watch.notify, ps5_watch.CRASH_FILE
    ps5_watch.notify = lambda cfg, title, *a, **k: sent.append((cfg["ntfy"]["topic"], title))
    ps5_watch.CRASH_FILE = tmp / "last_crash.json"
    cfg = {"ntfy": {"server": "https://ntfy.sh", "topic": "t1"}}
    try:
        ps5_watch.report_crash(cfg, KeyError("filters"))
        ps5_watch.report_crash(cfg, KeyError("filters"))
        assert sent == [("t1", "PS5 watcher: checks are CRASHING")], sent   # once, not every run
        assert "KeyError" in ps5_watch.CRASH_FILE.read_text()
        assert ps5_watch.clear_crash()["alerted"] and not ps5_watch.CRASH_FILE.exists()
        ps5_watch.report_crash(None, ValueError("bad yaml"))                 # config unreadable:
        assert len(sent) == 2 and sent[1][0]                                 # topic read from the file
    finally:
        ps5_watch.notify, ps5_watch.CRASH_FILE = orig


if __name__ == "__main__":
    test_canadacomputers_online_only()
    test_titles()
    test_price_and_seller()
    test_products_never_mixed()
    test_disc_console()
    test_bestbuy_online_only()
    test_alert_only_on_restock()
    test_pro_only()
    test_failing_store_slows_down()
    test_canadacomputers_backup_page()
    test_vanished_listing_alerts_again()
    test_cheapest_in_stock_price()
    test_staples_pages_in_turns()
    test_crash_is_reported()
    print("all matcher tests passed")
