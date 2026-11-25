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
]

CFG = {"filters": {"max_price": {"PS5 Digital": 850, "PS5 Pro": 1200}, "min_price": 300,
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


def test_bestbuy_pickup_only():
    """Sold out online but on the shelf at a Montreal store must count as in stock."""
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
            assert params.get("locations"), "pickup stores must be sent"
            return Resp({"availabilities": [avail("1", False, [("LaSalle", 2), ("Anjou", 0)]),
                                            avail("2", False, [("LaSalle", 0)]),
                                            avail("3", True, [])]})

    got = {o.id: o for o in ps5_watch.check_bestbuy(Session())}
    assert got["1"].in_stock and "LaSalle" in got["1"].stock_note and "Anjou" not in got["1"].stock_note
    assert not got["2"].in_stock                        # sold out everywhere
    assert got["3"].in_stock                            # online only


def test_canadacomputers_montreal_pickup():
    import ps5_watch

    def store(name, n):
        return (f'<div class="row"><span class="col-3 fm-SegoeUI-Bold">{name}</span>'
                f'<span class="ml-2 shop-online-box f-18">{n}</span></div>')

    page = ('<div id="checkothertores">' + store("Montreal", 0) + store("Brossard", 4)
            + store("Laval", 0) + store("Kingston", 1) + "</div>")

    class Resp:
        text = page
        def raise_for_status(self): pass

    class Session:
        def get(self, url, **k): return Resp()

    assert ps5_watch.cc_montreal_stock(Session(), "http://x") == {"Brossard": 4}  # Kingston ignored


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
        rewind(60); ps5_watch.run_once(cfg); assert len(calls) == 6
        assert sent == ["PS5 watcher: fake check is failing"], sent   # warned once, after an hour
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


if __name__ == "__main__":
    test_canadacomputers_montreal_pickup()
    test_titles()
    test_price_and_seller()
    test_products_never_mixed()
    test_bestbuy_pickup_only()
    test_alert_only_on_restock()
    test_pro_only()
    test_failing_store_slows_down()
    test_canadacomputers_backup_page()
    print("all matcher tests passed")
