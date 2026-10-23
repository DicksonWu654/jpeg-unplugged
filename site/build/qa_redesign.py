#!/usr/bin/env python3
"""Chrome presentation and network regression check against a locally served site.

Run: .venv/bin/python site/build/qa_redesign.py [BASE_URL] [SCREENSHOT_DIR]
Uses Chrome's network log, without request interception, to count real external
requests. CSP refusals and artwork errors are recorded separately from site errors.
"""
import json
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8794/"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "output/redesign")
OUT.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).resolve().parents[2]
GALLERY = json.loads((ROOT / "site/data/gallery.json").read_text())
CENSUS = json.loads((ROOT / "site/data/census.json").read_text())
MANIFEST = json.loads((ROOT / "site/gallery-assets/manifest.json").read_text())
TOTAL = len(GALLERY["items"])
assert {i["slug"] for i in GALLERY["items"]} == {i["slug"] for i in MANIFEST}
report = {"browser": "/usr/bin/google-chrome", "matrix": {}}
ARGS = ["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]


def external(url):
    parsed = urlsplit(url)
    return parsed.scheme in {"http", "https", "ws", "wss"} and parsed.netloc != urlsplit(BASE).netloc


def net_requests(path):
    log = json.loads(path.read_text())
    start = log["constants"]["logEventTypes"]["URL_REQUEST_START_JOB"]
    # Chrome's account, spellcheck and update services run outside the page.
    # The network isolation key identifies traffic from this top-level site,
    # including opaque sandbox frames. Browser service jobs have no initiating
    # origin ("not an origin"); no destination allowlist is used.
    origin = urlsplit(BASE).scheme + "://" + urlsplit(BASE).hostname
    jobs = [e["params"] for e in log["events"] if e["type"] == start
            and external(e.get("params", {}).get("url", ""))]
    site = [job["url"] for job in jobs
            if (origin in job.get("network_isolation_key", "") or origin in job.get("initiator", ""))
            and job.get("initiator") != "not an origin"]
    return site, len(jobs) - len(site)



def scroll(page, selector):
    page.locator(selector).evaluate("e=>e.scrollIntoView({behavior:'instant',block:'start'})")
    page.wait_for_timeout(250)


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth > innerWidth")


with sync_playwright() as p, tempfile.TemporaryDirectory(prefix="jpeg-redesign-") as scratch:
    for width in (390, 1440):
        for theme in ("light", "dark"):
            for mode in ("on", "off", "archive"):
                key = f"{width}-{theme}-{mode}"
                netlog = Path(scratch) / (key + ".json")
                browser = p.chromium.launch(executable_path=report["browser"], args=ARGS + ["--log-net-log=" + str(netlog)])
                ctx = browser.new_context(viewport={"width": width, "height": 844 if width == 390 else 900},
                                          color_scheme=theme, service_workers="block")
                page = ctx.new_page()
                errors, artwork_errors, attempted = [], [], []

                def console(msg):
                    if msg.type == "error":
                        url = msg.location.get("url", "")
                        (errors if url.startswith(BASE + "js/") else artwork_errors).append(msg.text[:160])

                def pageerror(err):
                    (errors if BASE + "js/" in (err.stack or "") else artwork_errors).append(str(err)[:160])

                page.on("console", console)
                page.on("response", lambda r: errors.append("HTTP " + str(r.status) + " " + r.url) if r.url.startswith(BASE) and r.status >= 400 else None)
                page.on("pageerror", pageerror)
                page.on("request", lambda req: attempted.append(req.url) if external(req.url) else None)
                page.goto(BASE + "?nosw&power=" + mode)
                page.wait_for_selector(".finding:nth-child(5)")
                page.add_style_tag(content="html{scroll-behavior:auto!important}")
                page.wait_for_function("document.fonts.status === 'loaded'")
                page.wait_for_timeout(1100)
                assert page.locator("#g-grid .tile").count() + page.locator("#g-all-grid .tile").count() == TOTAL
                assert page.locator("#gallery-all").get_attribute("open") is None
                assert not page.locator("#g-all-grid .tile").first.is_visible()
                assert not overflow(page), key
                assert page.locator("#hero + noscript + #gallery").count() == 1
                assert page.inner_text("#figure-n") == f"{CENSUS['survival']['yes']:,}"
                page.mouse.move(0, 0)
                if mode in ("on", "off"):
                    page.screenshot(path=str(OUT / f"{key}-hero.png"))
                scroll(page, "#gallery")
                page.wait_for_timeout(900)
                # Exercise a genuine plugged-to-unplugged transition and immediate thumbnail/verdict change.
                if mode == "on":
                    page.locator("#pill").click()
                    assert page.get_attribute("body", "data-power") == "off"
                    assert page.locator('.tile[data-slug="ab-1"]').evaluate("e=>e.classList.contains('is-broken')")
                    assert page.locator('.tile[data-slug="cryptopunks-data"]').evaluate("e=>e.classList.contains('is-survivor')")
                    assert page.locator('.tile[data-slug="ab-1"] img.thumb').get_attribute("src").endswith("_B.jpg")
                    page.locator("#pill").click()
                if mode == "off":
                    page.locator("#gallery").screenshot(path=str(OUT / f"{key}-featured-gallery.png"), style=".bar{visibility:hidden!important}")
                    scroll(page, "#findings")
                    page.locator("#findings").screenshot(path=str(OUT / f"{key}-finding-cards.png"), style=".bar{visibility:hidden!important}")
                    scroll(page, "#census")
                    page.screenshot(path=str(OUT / f"{key}-data.png"))
                    scroll(page, "#c-year")
                    page.screenshot(path=str(OUT / f"{key}-by-year.png"))
                # Every artwork is run in the viewer even on mobile, where tiles default to thumbnails.
                page.locator("#gallery-all summary").click()
                slugs = page.locator(".tile").evaluate_all("ts=>ts.map(t=>t.dataset.slug)")
                checked = 0
                for slug in slugs if mode != "on" else ["ab-1", "cryptopunks-data"]:
                    page.locator(f'.tile[data-slug="{slug}"] .tile-open').click()
                    page.wait_for_selector("#v-stage iframe")
                    page.wait_for_timeout(6500 if slug == "ab-145" else 130)
                    frame = page.locator("#v-stage iframe")
                    assert frame.get_attribute("sandbox") == "allow-scripts"
                    if mode != "on":
                        assert frame.get_attribute("csp").startswith("default-src 'none'")
                    if slug == "ab-1" and mode == "off":
                        page.wait_for_timeout(400)
                        assert "blocked" in page.inner_text("#v-log")
                        report.setdefault("genesis_unplugged_log", page.inner_text("#v-log"))
                    if slug == "ab-1" and mode == "archive":
                        assert "Restored" in page.inner_text("#v-verdict")
                    if slug == "ab-1" and width == 1440 and theme == "dark":
                        page.screenshot(path=str(OUT / f"{key}-genesis-live.png"))
                    page.keyboard.press("Escape")
                    checked += 1
                # Relevant data interactions and independent chart presence.
                address = page.evaluate("JU.data.collections.collections[0].address")
                page.locator("#f-q").fill(address)
                page.wait_for_timeout(200)
                assert page.locator("#coll-table tbody tr").count() == 1
                page.locator("#f-reset").click()
                assert f"{CENSUS['totals']['collections']:,}" in page.inner_text("#table-count")
                page.locator("#f-media").select_option("http")
                page.locator("#f-live").select_option("dead")
                page.locator('#coll-table th[data-k="holders"] button').click()
                assert page.locator('#coll-table th[data-k="holders"]').get_attribute("aria-sort")
                page.locator("#f-reset").click()
                for selector in ("#ch-where", "#ch-year svg", "#ch-gw", "#ch-claims", "#ch-hstatus", "#ch-htakeover", "#ch-pclass", "#ch-pfunnel", "#ch-ptime"):
                    assert page.locator(selector).is_visible(), selector
                hs = overflow(page)
                browser.close()
                requests, background_count = net_requests(netlog)
                row = {"horizontal_scroll": hs, "site_errors": errors, "live_artworks_checked": checked,
                       "external_request_count": len(requests),
                       "external_requests": [urlsplit(u)._replace(query="", fragment="").geturl() for u in requests], "browser_background_request_count": background_count,
                       "artwork_error_count": len(artwork_errors), "request_event_count": len(attempted)}
                report["matrix"][key] = row
                (OUT / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
                print(key, json.dumps(row), flush=True)
                assert not errors and not hs, key
                if mode != "on":
                    assert not requests, key + " external network traffic"
                else:
                    assert requests, key + " plugged positive control"
    # Shell, local fonts and previously viewed gallery remain usable offline.
    browser = p.chromium.launch(executable_path=report["browser"], args=ARGS)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
    page = ctx.new_page()
    page.goto(BASE)
    page.wait_for_selector(".finding:nth-child(5)")
    page.wait_for_function("navigator.serviceWorker.controller !== null")
    scroll(page, "#gallery")
    page.wait_for_timeout(400)
    automatic_frames = page.locator(".tile iframe").count()
    assert automatic_frames == 0
    report["reduced_motion"] = {"automatic_tile_iframes": automatic_frames}
    page.locator("#pill").click()
    page.locator('.tile[data-slug="ab-1"] .tile-open').click()
    page.wait_for_selector("#v-stage iframe")
    page.wait_for_timeout(600)
    page.keyboard.press("Escape")
    ctx.set_offline(True)
    page.reload()
    page.wait_for_selector(".finding:nth-child(5)")
    assert page.get_attribute("body", "data-power") == "off"
    assert page.locator("#g-grid .tile").count()
    assert page.evaluate("document.fonts.check('16px Silkscreen')")
    page.locator('.tile[data-slug="ab-1"] .tile-open').click()
    page.wait_for_selector("#v-stage iframe")
    report["offline"] = {"shell": True, "findings": True, "font": True, "viewed_gallery_live": True}
    browser.close()
(OUT / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
print("PASS", OUT / "verification.json")
