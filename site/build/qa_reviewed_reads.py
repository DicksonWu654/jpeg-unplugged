#!/usr/bin/env python3
"""Reviewed regression gate; exits nonzero on site errors or real external traffic.

Start .venv/bin/python -m http.server 8794 --bind 127.0.0.1 --directory site
Then .venv/bin/python site/build/qa_reviewed_reads.py [http://127.0.0.1:8794/]
Uses the repository's installed Playwright/Chromium, without downloading packages.
Artwork CSP refusals/runtime failures are recorded separately: demonstrating those
failures is the purpose of unplugged mode. They must never become network traffic.
"""
import json
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8794/"
ORIGIN = urlsplit(BASE).netloc
OUT = Path(tempfile.mkdtemp(prefix="nft-site-reviewed_reads-"))
# The dedicated headless build omits Chrome's unrelated account/update/autofill
# services, so the net-log can count every external URL without a host allowlist.
shells = list((Path.home() / ".cache/ms-playwright").glob(
    "chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"))
if not shells:
    sys.exit("No installed Chromium headless shell found in the Playwright cache.")
EXE = str(max(shells, key=lambda path: int(path.parents[1].name.rsplit("-", 1)[1])))
ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--no-sandbox"]
ROOT = Path(__file__).resolve().parents[2]
report = {"artifacts": str(OUT), "matrix": {}}


def external(url):
    parsed = urlsplit(url)
    return parsed.scheme in {"http", "https", "ws", "wss"} and parsed.netloc != ORIGIN


def network_requests(path):
    log = json.loads(path.read_text())
    start = log["constants"]["logEventTypes"]["URL_REQUEST_START_JOB"]
    return [e["params"]["url"] for e in log["events"]
            if e["type"] == start and external(e.get("params", {}).get("url", ""))]


with sync_playwright() as p:
    for width in (390, 1440):
        for theme in ("light", "dark"):
            for mode in ("off", "archive"):
                key = f"{width}-{theme}-{mode}"
                netlog = OUT / (key + "-net.json")
                browser = p.chromium.launch(executable_path=EXE, args=ARGS + ["--log-net-log=" + str(netlog)])
                context = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=theme,
                                              service_workers="block", reduced_motion="reduce")
                page = context.new_page()
                errors, artwork_errors, request_events = [], [], []

                def console(message):
                    if message.type != "error":
                        return
                    url = message.location.get("url", "")
                    (errors if url.startswith(BASE) else artwork_errors).append(message.text[:240])

                def pageerror(error):
                    (errors if BASE in (error.stack or "") else artwork_errors).append(str(error)[:240])

                page.on("console", console)
                page.on("pageerror", pageerror)
                page.on("request", lambda request: request_events.append(request.url) if external(request.url) else None)
                page.goto(BASE + "?power=" + mode + "&nosw")
                page.wait_for_function("window.JU && JU.data.headlines && document.querySelector('#ch-year svg')")
                page.wait_for_timeout(300)
                assert page.locator("#hero-answer").bounding_box()["y"] < 900
                assert "2.9%" in page.inner_text("#hero-answer")
                assert "63" in page.inner_text("#ch-fake")
                assert "142 of 147" in page.inner_text("#t-gw")
                labels = page.locator("#ch-year svg text").all_text_contents()
                assert "≤2020" in labels and "n=37" in labels
                assert all("n=" + str(n) in labels for n in (290, 1634, 648, 77, 78, 236))
                assert not any(y in labels for y in ("2017", "2018", "2019", "2020"))
                assert page.locator("#ch-htakeover .hrow .val").all_text_contents() == ["204", "309", "270", "58"]
                initial = page.evaluate("performance.getEntriesByType('resource').map(x=>({url:x.name,body:x.encodedBodySize,transfer:x.transferSize}))")
                assert not any("collections_extra" in r["url"] or "/evidence/" in r["url"] or "gallery.js" in r["url"] for r in initial)
                page.screenshot(path=str(OUT / (key + "-hero.png")))
                page.locator("#c-year").scroll_into_view_if_needed()
                page.screenshot(path=str(OUT / (key + "-year.png")))
                page.locator("#hosts").scroll_into_view_if_needed()
                page.screenshot(path=str(OUT / (key + "-hosts.png")))

                # Exercise the opt-in loader and confirm it stays out of the headline sample.
                page.locator("#f-extra").check()
                page.wait_for_function("JU.data.extra && !document.querySelector('#f-extra').disabled")
                assert "outside sample" in page.inner_text("#table-count")
                page.locator("#f-extra").uncheck()
                assert "3,000" in page.inner_text("#table-count")

                page.locator("#gallery").scroll_into_view_if_needed()
                page.wait_for_selector(".tile")
                slugs = page.locator(".tile").evaluate_all("tiles=>tiles.map(t=>t.dataset.slug)")
                assert len(slugs) == 83
                # The viewer forces a live render even on mobile/reduced-motion.
                # Exercise every asset, including A-Frame's delayed hand-model fetch.
                for slug in slugs:
                    page.locator('.tile[data-slug="' + slug + '"] .tile-open').click()
                    page.wait_for_selector("#v-stage iframe")
                    page.wait_for_timeout(8000 if slug == "ab-145" else 180)
                    frame = page.locator("#v-stage iframe")
                    assert frame.get_attribute("csp")
                    assert frame.get_attribute("sandbox") == "allow-scripts"
                    if slug == "ab-145":
                        policy = frame.content_frame.locator('head meta[http-equiv="Content-Security-Policy"]')
                        assert policy.count() == 1
                    page.keyboard.press("Escape")
                overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
                browser.close()  # flush Chromium's network log before counting
                requests = network_requests(netlog)
                row = {
                    "initial_body_bytes": sum(r["body"] for r in initial),
                    "initial_transfer_bytes": sum(r["transfer"] for r in initial),
                    "live_artworks_tested": len(slugs), "horizontal_overflow": overflow,
                    "site_errors": errors, "external_request_count": len(requests),
                    "external_requests": requests, "blocked_request_events": len(request_events),
                    "artwork_error_count": len(artwork_errors), "artwork_error_sample": artwork_errors[:3],
                }
                report["matrix"][key] = row
                (OUT / "results.json").write_text(json.dumps(report, indent=2))
                print(key, json.dumps(row), flush=True)
                assert not errors and not requests and not overflow, key

print("PASS; report:", OUT / "results.json")
