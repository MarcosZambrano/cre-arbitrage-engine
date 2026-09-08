# Architecture — the browser access layer

LoopNet sits behind Akamai Bot Manager. Most of the engineering in this project is in getting a
page to load at all; the scraping itself is ordinary Selenium once a session exists.

Everything below was established empirically, by testing each hypothesis against the live site.
None of it is inferable from reading the code, which is why it is written down.

## The core decision: attach, never spawn

A browser that ChromeDriver launches itself is rejected. It runs on a blank profile with no cookie
history and advertises automation flags, and Akamai returns `Access Denied` at the edge — before any
page logic runs. (`robots.txt` returns 403 to non-browser clients too, so the rejection is
infrastructural, not application-level.)

So `BrowserManager` does not let Selenium start anything:

1. `start_chrome()` launches an ordinary `chrome.exe` via `subprocess.Popen`, with
   `--remote-debugging-port=9222` and a persistent `--user-data-dir`.
2. Selenium connects to that process with
   `chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")`.

The result is a genuine browser with a genuine profile, driven remotely. `--no-first-run` and
`--no-default-browser-check` are required, not cosmetic: without them a brand-new profile opens
Chrome's welcome screen and **silently ignores the URL argument**.

The launch uses `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` (plus `CREATE_BREAKAWAY_FROM_JOB`,
with a fallback for environments that forbid it) so Chrome outlives the Python process and the next
run can reuse the warmed session.

## Timing: the port is ready long before the page is

The debugging port binds 1–2 seconds after launch. Akamai's JavaScript challenge needs roughly
15–20 seconds more. While it runs, the tab title is the bare host, `loopnet.com` — neither the real
page nor a block.

**Attaching ChromeDriver during that window fails the challenge and burns the profile permanently.**
Measured directly: identical profiles left alone cleared in ~18s every time, while the same profile
driven by Selenium at t+5s was denied.

So the wait is passive. `wait_for_challenge_via_devtools()` polls Chrome's
`http://127.0.0.1:9222/json/list` endpoint — a plain HTTP read of the DevTools target list that
reports tab titles **without opening a CDP session**. Only once the title reads `LoopNet` does
Selenium attach.

## Navigation restarts the browser

The same failure applies to every page load, not just the first:

> Any navigation performed in a browser ChromeDriver has attached to re-runs the challenge under an
> active CDP session, fails it, and burns the profile.

Interacting with an already-loaded page is fine — clicking, reading, typing. It is specifically
*navigation* that fails.

Crucially, **the taint outlives `driver.quit()`**. Ending the Selenium session and then navigating
over the DevTools HTTP endpoint still gets Access Denied. Three measurements pin this down:

| Sequence | Result |
|---|---|
| Chrome launched at the URL, never attached | loads |
| Attached, `quit()`, then navigate without CDP | **Access Denied** |
| Attached, `quit()`, kill Chrome, relaunch **same profile** at the URL | loads |

The third line is the important one: the *profile* is not tainted, only the live browser session.
So `BrowserManager.navigate()` restarts Chrome on the target URL, waits for the challenge passively,
and re-attaches — reusing the same profile and its cookies throughout.

It costs roughly 20–30 seconds per navigation. That is the price of the only sequence that works,
and it is why the scraper builds a filtered results URL instead of clicking through the UI: each
avoided page load is one fewer relaunch and one fewer chance to burn the profile.

This also produced a confusing symptom earlier: the scraper worked once, then never again. After a
successful run the URL had become `/search/...`, so an exact `current_url != URL` comparison fired a
`driver.get()` reload on the next run. The guard is now a host check
(`"loopnet.com" not in current_url`).

## Burned profiles, and recovery

A rejected profile receives a poisoned `_abck` cookie. That state lives in its cookie database and
is **permanent** — no amount of waiting or retrying recovers it, and it is per-profile, not per-IP.
A clean profile from the same machine and network gets through immediately.

`run()` therefore self-heals rather than failing:

1. `wait_for_real_page()` returns `False` on `Access Denied`.
2. `close_chrome_for_profile()` terminates only the Chrome processes whose command line contains
   that profile directory. `driver.quit()` is **not** sufficient — Selenium only attached to this
   browser, so quitting the session leaves the process alive and the port open, and the next launch
   reattaches to the same burned browser.
3. `delete_profile()` removes the directory, reclaiming 100–250 MB.
4. A fresh timestamped profile is created and the whole sequence retries once.

If a brand-new profile is also blocked, the cause is the network rather than the profile, and the
program says so instead of rotating forever.

`delete_profile()` is deliberately defensive, since it is an unattended recursive delete: the path
must resolve strictly inside the profile root, must not be the root itself, and must contain
`Local State` or `Default` to look like a real Chrome profile. Failure is never fatal.

## Never call `driver.quit()`

Selenium did not start this browser. Quitting discards the warmed session — the accumulated cookies
that got past the challenge — while leaving the process running. The program simply exits and leaves
the browser open for the next run.

## Clicking: JavaScript, not native

`select_property_type()` clicks via `execute_script("arguments[0].click();", tile)` rather than
`tile.click()`.

A native click is delivered to the pixel at the element's centre, and `div.new-quick-search-wrap`
overlays the property-type carousel — so the click reaches the overlay and never triggers Angular's
`ng-click`. Selenium reports success, and nothing happens. A JavaScript click dispatches the event
directly on the element, bypassing hit-testing, and additionally reaches tiles scrolled outside the
carousel viewport (Restaurant, Lab) that a native click cannot touch at all.

Two related traps in that widget:

- **`.text` returns `""` for all nine labels.** The `<p>` elements are visually hidden, and `.text`
  reads rendered text. `get_attribute("textContent")` reads the DOM instead.
- **`ancestor::` returns the outermost match.** `//p[text()='X']/ancestor::div[contains(@class,
  'property-type')]` resolves to the `property-type-icons` **carousel**, not the tile — because
  `find_element` takes the first ancestor in document order, and `"property-type"` is a substring of
  `"property-type-icons"`. Clicking that hits the carousel's centre, which is why every property
  type selected the same tile. The predicate form `[.//p[...]]` selects the tile itself.

## Searching by URL, not by the form

The search is issued as a URL rather than by filling in the homepage form, because the form's
submit — and the filter panel's Search button — are navigations, and
[navigations restart the browser](#navigation-restarts-the-browser). Driving the UI would mean
paying a relaunch per interaction and hitting the bot wall at the final click.

`LoopNetScraper.search_url()` builds the address directly:

```
https://www.loopnet.com/search/industrial-space/dallas-tx/for-lease/
    ?max-rent=500000&min-space-size=25000
```

This removes the homepage round-trip, the property-type click and the location typeahead, taking the
run from two navigations to one.

### The location slug

LoopNet uses two different separators, both verified live:

| Input | Slug | Rule |
|---|---|---|
| `Dallas, TX` | `dallas-tx` | US: single dash + two-letter state code |
| `San Francisco, California` | `san-francisco-ca` | full state names are mapped to codes |
| `Paris, France` | `paris--france` | international: **double** dash + country |
| `Austin` | `austin` | no region given |

`location_slug()` implements this, stripping accents via `unicodedata` so `Zürich` becomes `zurich`.

Non-US coverage is LoopNet's own limitation, not a slug bug: `paris--france` and `berlin--germany`
resolve, while `london--united-kingdom`, `toronto--canada` and `milan--italy` return 404 under every
spelling tried. `search()` detects a 404 title and says so rather than scraping an error page.
