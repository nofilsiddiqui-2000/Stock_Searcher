# Stock Searcher

A small, free, local-only stock watcher for Canadian retailers. It checks stores on a
schedule and alerts you the moment a product you want is **in stock, sold by the store
itself, and under your price limit**. It only alerts. It never buys anything.

It was built to catch a PS5 restock (currently set up for the **PS5 Pro**, with the
**PS5 Digital Edition** ready to switch back on). The parts are generic, so it can be
reused for other hard-to-find products; see [Reusing it](#reusing-it-for-other-products).

## What you get
- **Phone alert** through the free [ntfy](https://ntfy.sh) app, with a link straight to the product page.
- **Laptop alarm**: a loud looping sound and an always-on-top pop-up (Yes opens the product page).
- **One alert per restock**, not one every check. If the item sells out and comes back, you get another.
- **Status screen** in the terminal (`--status`, `--live`): last check per store, what was found,
  and the last time each product was available.
- **Stock history**: every restock and sell-out is added to `stock_history.csv`.
- **Broken-check warning**: if a store keeps failing for about an hour, you get a notification
  instead of silently missing stock.

## Stores
| Store | How it's checked | In-store pickup | Every |
|---|---|---|---|
| Best Buy Canada | the site's own JSON search + availability API; marketplace sellers ignored | yes, 42 Montreal-area stores | 5 min |
| Canada Computers | PlayStation category page + product page store list | yes, 4 Montreal-area stores | 5 min |
| Staples.ca | fixed product pages; must say "Delivery available" | no | 20 min |
| Walmart.ca | search page; only listings **sold by Walmart** | no | 20 min |
| Amazon.ca | search limited to **sold by Amazon.ca** | no | 20 min |
| EB Games | not supported: its bot check blocks automated browsers | – | – |

Staples, Walmart and Amazon block plain requests, so they are opened in a normal, visible
Microsoft Edge window (Playwright) for about a minute. **The watcher never tries to get
past a CAPTCHA or bot check**: if a store blocks it, that check just counts as failed and
is retried next time.

## Setup (Windows)
Needs Python 3.12+ and Microsoft Edge.

```powershell
pip install requests lxml pyyaml playwright
copy config.example.yaml config.yaml     # then edit config.yaml
python test_matcher.py                   # should print "all matcher tests passed"
python ps5_watch.py --test-alert         # phone notification + laptop alarm
powershell -ExecutionPolicy Bypass -File .\install_task.ps1
```

1. In `config.yaml`, set `ntfy.topic` to a long random name. Anyone who knows it can read
   your alerts.
2. On your phone, install **ntfy**, tap **+** and subscribe to that topic (server ntfy.sh).
   On Android, turn on **Instant delivery** for the topic and set the app's battery use to
   **Unrestricted**, or alerts only show up when you open the app.
3. `install_task.ps1` adds a Windows Task Scheduler task, "PS5 Stock Watch", that runs a check
   every 5 minutes while you're logged in. Re-run it after moving the folder.

Optional shortcut: add this to your PowerShell profile (`notepad $PROFILE`) so `ps5` and
`ps5 --live` work from any terminal:
```powershell
function ps5 { python "C:\path\to\ps5_watch.py" --status @args }
```

## Commands
```powershell
python ps5_watch.py --status         # is it running, last check per store, what's in stock
python ps5_watch.py --status --live  # same, refreshing every 30 s (Ctrl+C to quit)
python ps5_watch.py --dry-run        # check every store now, print what was seen, no alerts
python ps5_watch.py --test-alert     # test the phone notification and the laptop alarm
python test_matcher.py               # run the tests
```
`status.cmd` opens the live status by double-click.

Stop the watcher: `Unregister-ScheduledTask -TaskName "PS5 Stock Watch" -Confirm:$false`

## Settings (`config.yaml`)
| Setting | What it does |
|---|---|
| `filters.max_price` | the products being watched, each with its price limit (before tax). Comment a line out to stop watching it. |
| `filters.min_price` | anything cheaper is treated as an accessory (stands, covers, fans), never alerted |
| `filters.first_party_only` | ignore marketplace / third-party sellers |
| `retailers` | turn each store on or off |
| `laptop_alarm` | play the alarm and show the pop-up on this computer |
| `browser_check_minutes` | how often the Edge-window stores are checked |
| `failure_alert_after` | failed checks in a row before you're warned |

## Files
| File | |
|---|---|
| `ps5_watch.py` | everything: product matching, store checks, alerts, history, status screen |
| `test_matcher.py` | tests, using real listing titles and fake stores (no network) |
| `config.example.yaml` | settings template; your own copy is `config.yaml` (not in git) |
| `install_task.ps1` | installs the scheduled task |
| `status.cmd` | double-click live status |

Created while running (not in git): `state.json` (what's in stock, failures, history),
`ps5_watch.log`, `stock_history.csv`.

## How it works
Each run (`run_once` in `ps5_watch.py`):
1. Every enabled store returns a list of `Offer`s: title, price, URL, in stock or not,
   sold by the store or not, and a short stock note.
2. `product_of(title)` decides which product a listing is (or none). Each product has its own
   title matcher (`is_ps5_pro`, `is_ps5_digital`) that excludes look-alikes such as
   refurbished/open-box units, other models and accessories.
3. `passes_filters` applies the price limits and the seller rule.
4. A listing that passes and is in stock, and wasn't on the previous run, triggers the alarm and
   the phone alert, and starts a history entry. When it's gone, the history entry is closed.
5. Stores that always list the product (sold out or not) must show at least one listing.
   Zero listings means the page changed, which counts as a failed check, not "sold out".

## Reusing it for other products
Everything product-specific is in `ps5_watch.py`, near the top of each section:

1. **Recognise the product**: write an `is_<product>(title)` matcher next to `is_ps5_pro`, add
   the name to `PRODUCTS`, and add it to `product_of`. Add real titles (including look-alikes
   that must *not* match) to `test_matcher.py`.
2. **Tell each store where to look**: add search words for it in `SEARCHES`, product page URLs in
   `STAPLES_PRODUCTS`, and change `CC_PLAYSTATION_PAGE` (Canada Computers category page) if it's
   in another category.
3. **Set the price**: add `<product name>: <limit>` under `filters.max_price` in `config.yaml`, and
   adjust `min_price` so accessories stay out.
4. **Pickup stores** (optional): `BESTBUY_PICKUP_STORES` (Best Buy store IDs) and
   `CC_MONTREAL_STORES` are set to Montreal; change them to your area.
5. Run `python test_matcher.py` and `python ps5_watch.py --dry-run` and compare against the
   stores' websites before relying on it.

New store: write a `check_<store>(session_or_page, queries)` function that returns `Offer`s and
add it to `HTTP_RETAILERS` (plain requests) or `BROWSER_RETAILERS` (needs the Edge window).

## Things to know
- It only runs while the computer is **on, awake and logged in**. No checks happen while it sleeps.
- Stores change their pages. If a store shows **FAILED** on the status screen for a while, its
  page probably changed and its check function needs updating.
- Checking too often can get you blocked. Canada Computers once refused its search page to
  this connection after a few hours of 5-minute checks, which is why its category page is used.
- Times in the history are accurate to the check interval.
