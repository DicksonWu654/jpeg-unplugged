#!/usr/bin/env python3
"""End-to-end checks for the site. Serves nothing itself: start `python -m http.server 8791` in site/ first.

  .venv/bin/python site/build/qa.py [BASE_URL] [SHOT_DIR]

Checks: (1) the toggle really blocks the network, measured with Chromium's own net-log (requests the browser's network
stack made to the CDN hosts), plugged vs unplugged; (2) no console/page errors from the site's own code; (3) the three
gallery modes; (4) table search/sort; (5) viewer; (6) real `offline` event flips the page; (7) desktop/mobile/dark screenshots.
"""
import json
import os
import re
import sys
import tempfile
from playwright.sync_api import sync_playwright

EXE = os.path.expanduser("~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome")
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8791/index.html"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("notes/site-shots")
os.makedirs(SHOTS, exist_ok=True)
EXT = ["cdnjs.cloudflare.com", "unpkg.com", "cdn.aframe.io", "api.ipify.org"]
ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--no-sandbox"]
results = {}


def launch(p, netlog=None):
    args = list(ARGS)
    if netlog:
        args += ["--log-net-log=" + netlog, "--net-log-capture-mode=Everything"]
    return p.chromium.launch(executable_path=EXE, args=args)


def external_requests(netlog):
    """URLs the browser's network stack requested for the external hosts (CSP-blocked requests never get here)."""
    txt = open(netlog, errors="ignore").read()
    urls = set(re.findall(r'"url":"(https?://[^"]+)"', txt))
    return sorted(u for u in urls if any(h in u for h in EXT))


def scroll_gallery(pg, seconds_per_step=1.4):
    pg.evaluate("document.querySelector('#g-grid').scrollIntoView()")
    pg.wait_for_selector(".tile")
    n = pg.evaluate("document.querySelectorAll('.tile').length")
    pg.wait_for_timeout(12000)  # dwell on the first rows (the Art Blocks pieces that need CDN scripts)
    total = pg.evaluate("document.documentElement.scrollHeight")
    y = pg.evaluate("window.scrollY")
    step = 600
    end = pg.evaluate("document.querySelector('#g-grid').getBoundingClientRect().bottom + window.scrollY")
    seen = {}
    for slug, txt in pg.evaluate("Array.from(document.querySelectorAll('.tile')).map(t=>[t.dataset.slug,t.querySelector('.tile-live').textContent]).filter(x=>x[1])"):
        seen[slug] = txt
    while y < end:
        y += step
        pg.evaluate(f"window.scrollTo(0,{y})")
        pg.wait_for_timeout(int(seconds_per_step * 1000))
        for slug, txt in pg.evaluate("Array.from(document.querySelectorAll('.tile')).map(t=>[t.dataset.slug,t.querySelector('.tile-live').textContent]).filter(x=>x[1])"):
            seen[slug] = txt
    scroll_gallery.seen = seen
    return n


def run_mode(p, query):
    with tempfile.TemporaryDirectory() as d:
        nl = os.path.join(d, "net.json")
        b = launch(p, nl)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, service_workers="block")
        pg = ctx.new_page()
        own_errors, frame_errors = [], []
        pg.on("pageerror", lambda e: (own_errors if "127.0.0.1" in (e.stack or "") else frame_errors).append(str(e)[:160]))
        pg.on("console", lambda m: (own_errors if m.type == "error" and "127.0.0.1:8791/js" in json.dumps(m.location) else frame_errors).append(m.text[:140]) if m.type == "error" else None)
        pg.goto(BASE + query)
        pg.wait_for_timeout(1200)
        n = scroll_gallery(pg)
        live = pg.evaluate("Array.from(document.querySelectorAll('.tile')).filter(t=>t.querySelector('iframe')).length")
        seen = scroll_gallery.seen
        blocked_txt = len(seen)
        sample = list(seen.items())[:4]
        b.close()
        reqs = external_requests(nl)
        return {"tiles": n, "tiles_with_report_text": blocked_txt, "external_requests": reqs, "own_errors": own_errors, "frame_errors_sample": frame_errors[:4], "report_sample": sample}


with sync_playwright() as p:
    # 1. the toggle blocks the network (measured by the browser's net stack)
    results["plugged"] = run_mode(p, "")
    results["unplugged"] = run_mode(p, "?power=off")
    results["archive"] = run_mode(p, "?power=archive")

    # 2. interaction + screenshots
    b = launch(p)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, service_workers="block")
    pg = ctx.new_page()
    own = []
    pg.on("pageerror", lambda e: own.append(str(e)[:200]) if "127.0.0.1" in (e.stack or "") else None)
    pg.on("console", lambda m: own.append(m.text[:200]) if m.type == "error" and "127.0.0.1:8791" in json.dumps(m.location) else None)
    pg.goto(BASE)
    pg.wait_for_timeout(1500)
    results["sample_banner_visible"] = pg.is_visible("#sample-banner")
    results["hero_figure_on"] = pg.inner_text("#figure")
    pg.screenshot(path=f"{SHOTS}/desktop_hero_plugged.jpg", type="jpeg", quality=72)
    pg.click("#plug-btn")
    pg.wait_for_timeout(2500)
    results["hero_figure_off"] = pg.inner_text("#figure")
    results["body_power_after_click"] = pg.get_attribute("body", "data-power")
    results["pill_aria"] = pg.get_attribute("#pill", "aria-checked")
    pg.screenshot(path=f"{SHOTS}/desktop_hero_unplugged.jpg", type="jpeg", quality=72)
    pg.evaluate("document.querySelector('#census').scrollIntoView()")
    pg.wait_for_timeout(800)
    pg.evaluate("window.scrollBy(0, 330)")
    pg.wait_for_timeout(900)
    pg.screenshot(path=f"{SHOTS}/desktop_census_unplugged.jpg", type="jpeg", quality=72)
    pg.evaluate("document.querySelector('#c-year').scrollIntoView()")
    pg.wait_for_timeout(600)
    pg.screenshot(path=f"{SHOTS}/desktop_year_unplugged.jpg", type="jpeg", quality=72)

    # table
    pg.evaluate("document.querySelector('#c-table').scrollIntoView()")
    pg.fill("#f-q", "FWAP")
    pg.wait_for_timeout(500)
    results["table_search_rows"] = pg.evaluate("document.querySelectorAll('#coll-table tbody tr').length")
    pg.click("#f-reset")
    pg.select_option("#f-media", "http")
    pg.select_option("#f-live", "dead")
    pg.wait_for_timeout(300)
    results["table_filter_text"] = pg.inner_text("#table-count")
    pg.click("#coll-table th[data-k=holders] button")
    pg.wait_for_timeout(200)
    results["table_sort_aria"] = pg.get_attribute("#coll-table th[data-k=holders]", "aria-sort")
    pg.click("#f-reset")
    pg.wait_for_timeout(300)
    pg.screenshot(path=f"{SHOTS}/desktop_table.jpg", type="jpeg", quality=72)

    # viewer
    pg.evaluate("document.querySelector('#g-grid').scrollIntoView()")
    pg.wait_for_timeout(2500)
    pg.click(".tile[data-slug=ab-1] .tile-open")
    pg.wait_for_timeout(4000)
    results["viewer_open"] = pg.evaluate("document.querySelector('#viewer').open")
    results["viewer_log"] = pg.inner_text("#v-log")[:300]
    pg.screenshot(path=f"{SHOTS}/desktop_viewer_unplugged.jpg", type="jpeg", quality=72)
    pg.click("#viewer .seg3[data-mode=archive]")
    pg.wait_for_timeout(4500)
    results["viewer_verdict_archive"] = pg.inner_text("#v-verdict")
    pg.screenshot(path=f"{SHOTS}/desktop_viewer_archive.jpg", type="jpeg", quality=72)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)

    # gallery mode buttons
    pg.click(".g-power .seg3[data-mode=on]")
    pg.wait_for_timeout(500)
    results["mode_after_gallery_button"] = pg.get_attribute("body", "data-power")
    results["own_errors"] = own
    b.close()

    # 3. real offline event flips the page
    b = launch(p)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, service_workers="block")
    pg = ctx.new_page()
    pg.goto(BASE)
    pg.wait_for_timeout(1200)
    before = pg.get_attribute("body", "data-power")
    ctx.set_offline(True)
    pg.wait_for_timeout(800)
    results["offline_flip"] = [before, pg.get_attribute("body", "data-power"), pg.is_visible("#toast")]
    b.close()

    # 4. mobile 375
    b = launch(p)
    ctx = b.new_context(viewport={"width": 375, "height": 812}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
    pg = ctx.new_page()
    own = []
    pg.on("pageerror", lambda e: own.append(str(e)[:200]) if "127.0.0.1" in (e.stack or "") else None)
    pg.goto(BASE)
    pg.wait_for_timeout(1500)
    results["mobile_hscroll"] = pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    pg.screenshot(path=f"{SHOTS}/mobile_hero_plugged.jpg", type="jpeg", quality=70)
    pg.click("#plug-btn")
    pg.wait_for_timeout(2500)
    pg.screenshot(path=f"{SHOTS}/mobile_hero_unplugged.jpg", type="jpeg", quality=70)
    pg.evaluate("document.querySelector('#c-where').scrollIntoView()")
    pg.wait_for_timeout(700)
    pg.screenshot(path=f"{SHOTS}/mobile_census.jpg", type="jpeg", quality=70)
    pg.evaluate("document.querySelector('#c-year').scrollIntoView()")
    pg.wait_for_timeout(700)
    pg.screenshot(path=f"{SHOTS}/mobile_year.jpg", type="jpeg", quality=70)
    pg.evaluate("document.querySelector('#g-grid').scrollIntoView()")
    pg.wait_for_timeout(2500)
    results["mobile_live_iframes"] = pg.evaluate("document.querySelectorAll('.tile iframe').length")
    results["mobile_run_buttons"] = pg.evaluate("document.querySelectorAll('.tile-run').length")
    pg.screenshot(path=f"{SHOTS}/mobile_gallery.jpg", type="jpeg", quality=70)
    pg.click(".tile[data-slug=ab-1] .tile-run")
    pg.wait_for_timeout(3500)
    results["mobile_after_run_iframes"] = pg.evaluate("document.querySelectorAll('.tile iframe').length")
    pg.evaluate("document.querySelector('#table-count').scrollIntoView()")
    pg.wait_for_timeout(500)
    pg.screenshot(path=f"{SHOTS}/mobile_table.jpg", type="jpeg", quality=70)
    results["mobile_hscroll_end"] = pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    results["mobile_own_errors"] = own
    b.close()

    # 5. dark scheme
    b = launch(p)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark", service_workers="block")
    pg = ctx.new_page()
    pg.goto(BASE + "?power=off")
    pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('#c-where').scrollIntoView()")
    pg.wait_for_timeout(900)
    pg.screenshot(path=f"{SHOTS}/desktop_dark_census.jpg", type="jpeg", quality=72)
    pg.evaluate("document.querySelector('#c-year').scrollIntoView()")
    pg.wait_for_timeout(700)
    pg.screenshot(path=f"{SHOTS}/desktop_dark_year.jpg", type="jpeg", quality=72)
    b.close()

    # 6. reduced motion: thumbnails only
    b = launch(p)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce", service_workers="block")
    pg = ctx.new_page()
    pg.goto(BASE)
    pg.wait_for_timeout(1000)
    pg.evaluate("document.querySelector('#g-grid').scrollIntoView()")
    pg.wait_for_timeout(2500)
    results["reduced_motion_iframes"] = pg.evaluate("document.querySelectorAll('.tile iframe').length")
    b.close()

    # 7. widths x themes: no sideways scroll, no console errors, new sections render
    sweep = {}
    for w in (360, 390, 768, 1440):
        for th in ("light", "dark"):
            b = launch(p)
            ctx = b.new_context(viewport={"width": w, "height": 900}, color_scheme=th, service_workers="block", reduced_motion="reduce")
            pg = ctx.new_page()
            errs = []
            pg.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append("pageerror " + str(e)[:160]))
            pg.goto(BASE)
            pg.wait_for_timeout(2500)
            hs = pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            ids = {i: pg.evaluate("(function(){var e=document.getElementById('%s');return !!e && !e.hidden})()" % i) for i in ("census", "pen", "hosts", "gallery", "method")}
            if w in (360, 390):
                for sid in ("pen",):
                    pg.evaluate("document.getElementById('%s').scrollIntoView({behavior:'instant'})" % sid)
                    pg.wait_for_timeout(400)
                    pg.screenshot(path=f"{SHOTS}/{sid}_{w}_{th}.jpg", type="jpeg", quality=70)
            sweep[f"{w}-{th}"] = {"hscroll": hs, "errors": errs, "visible_sections": [k for k, v in ids.items() if v]}
            b.close()
    results["sweep"] = sweep

print(json.dumps(results, indent=1))
