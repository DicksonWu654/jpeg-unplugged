"""Three-condition headless-Chromium renderer for on-chain artworks.

  A  normal      : full network
  B  unplugged   : every non-document request aborted (and DNS blackholed); page gets only the bytes from the chain
  C  unplug+arch : like B, but URLs found in data/dep-archive/MANIFEST.json are served from the local archive

Every request attempt is logged (url, resource type, action, status/failure). Usage:
    render.py <slug> [--conds A,B,C] [--delay 4] [--viewport 800]
Reads data/gallery/<slug>/meta.json + artwork.<ext> ; writes screenshots, request logs, console logs, result.json.
"""
import argparse, glob, hashlib, json, mimetypes, os, pathlib, sys, time
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAL = ROOT / "data" / "gallery"
ARCH = ROOT / "data" / "dep-archive"
BASE = "https://onchain.invalid/"           # synthetic origin; document is fulfilled from chain bytes
CHROME = glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome"))[-1]
ARGS = ["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
        "--autoplay-policy=no-user-gesture-required", "--mute-audio", "--disable-background-timer-throttling"]
SEED_JS = """(()=>{let s=0x2545F491;const r=()=>{s^=s<<13;s^=s>>>17;s^=s<<5;return ((s>>>0)%1000003)/1000003};
Math.random=r;})();"""   # same deterministic Math.random in every condition (artworks seed from the chain hash, not from this)


def load_archive():
    m = ARCH / "MANIFEST.json"
    if not m.exists():
        return {}
    return {e["url"]: e for e in json.loads(m.read_text())["entries"] if e.get("archived")}


def run_condition(pw, cond, doc_bytes, doc_type, archive, viewport, delay, out_prefix, settle_ms=15000):
    log, console, errors = [], [], []
    browser_args = list(ARGS)
    if cond in "BC":
        browser_args.append("--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE onchain.invalid")
    browser = pw.chromium.launch(executable_path=CHROME, args=browser_args)
    ctx = browser.new_context(viewport={"width": viewport, "height": viewport}, service_workers="block")
    ctx.add_init_script(SEED_JS)
    t0 = time.time()
    by_req = {}

    def handler(route):
        req = route.request
        url = req.url
        rec = {"t": round(time.time() - t0, 3), "url": url[:500], "type": req.resource_type, "method": req.method,
               "frame": req.frame.url[:120] if req.frame else None}
        by_req[id(req)] = rec
        log.append(rec)
        if url == BASE:
            rec["action"] = "served-from-chain"
            return route.fulfill(status=200, body=doc_bytes, headers={"content-type": doc_type})
        if url == BASE + "favicon.ico":
            rec["action"] = "ignored-favicon"
            return route.fulfill(status=204, body=b"")
        if url.startswith(BASE):  # relative reference to a sibling of the synthetic origin: nothing on chain
            rec["action"] = "blocked-no-such-file"
            return route.fulfill(status=404, body=b"")
        if cond == "A":
            rec["action"] = "allowed"
            return route.continue_()
        if cond == "C" and url in archive:
            e = archive[url]
            p = ARCH / "files" / e["file"]
            rec["action"] = "archive"; rec["sha256"] = e["sha256"]
            return route.fulfill(status=200, body=p.read_bytes(),
                                 headers={"content-type": e["content_type"], "access-control-allow-origin": "*"})
        rec["action"] = "blocked"
        return route.abort("blockedbyclient")

    ctx.route("**/*", handler)
    page = ctx.new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text[:400]}) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: errors.append(str(e)[:400]))

    def on_resp(resp):
        rec = by_req.get(id(resp.request))
        if rec is not None:
            rec["status"] = resp.status
            try:
                rec["bytes"] = len(resp.body()) if resp.request.resource_type != "document" else None
            except Exception:
                pass
    page.on("response", on_resp)

    def on_fail(req):
        rec = by_req.get(id(req))
        if rec is not None:
            rec["failure"] = req.failure
    page.on("requestfailed", on_fail)
    nav_err = None
    try:
        page.goto(BASE, wait_until="load", timeout=60000)
    except Exception as e:  # noqa
        nav_err = str(e)[:300]
    try:
        page.wait_for_load_state("networkidle", timeout=settle_ms)
    except Exception:
        pass
    page.wait_for_timeout(int(delay * 1000))
    dom = {}
    try:
        dom = page.evaluate("""()=>({canvas:document.querySelectorAll('canvas').length,svg:document.querySelectorAll('svg').length,
          img:document.querySelectorAll('img').length, iframe:document.querySelectorAll('iframe').length,
          body_text:(document.body&&document.body.innerText||'').slice(0,200), title:document.title,
          fonts:[...document.fonts].map(f=>f.family+':'+f.status).slice(0,20)})""")
    except Exception as e:
        dom = {"error": str(e)[:200]}
    shot = str(out_prefix) + ".png"
    page.screenshot(path=shot, full_page=False)
    page.wait_for_timeout(1700)
    page.screenshot(path=str(out_prefix) + "_late.png", full_page=False)   # second frame: measures how much the artwork animates by itself
    browser.close()
    for r in log:
        r.setdefault("status", None)
    return dict(log=log, console=console, errors=errors, dom=dom, nav_error=nav_err, shot=shot)


# ---------------------------------------------------------------------------------- image analysis
def load_arr(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.int16)


def blank_stats(arr):
    """fraction of pixels that differ from the modal colour; plus colour count"""
    flat = arr.reshape(-1, 3)
    key = flat[:, 0].astype(np.int32) * 65536 + flat[:, 1].astype(np.int32) * 256 + flat[:, 2]
    vals, cnt = np.unique(key, return_counts=True)
    modal = vals[cnt.argmax()]
    m = np.array([(modal >> 16) & 255, (modal >> 8) & 255, modal & 255])
    ink = float((np.abs(arr - m).max(axis=2) > 6).mean())   # pixels visibly different from the modal colour
    return dict(non_bg_frac=round(ink, 5), n_colors=int(len(vals)), modal=f"{int(modal):06x}")


def diff_frac(a, b, thr=32):
    d = np.abs(a - b).max(axis=2)
    return float((d > thr).mean())


def verdict(A, A2, B, C=None, Alate=None):
    """Return dict of metrics+verdicts. Thresholds are documented in docs/methods/gallery.md.
    noise = how much A differs from itself (second run, and second frame 1.7 s later in the same page): captures animation/timing.
    A condition X is 'identical' if min(diff to A, A2, Alate) <= max(1%, 1.5*noise) ; 'broken' if blank where A has ink, or <25% of A's ink; else 'degraded'."""
    a, a2, b = load_arr(A), load_arr(A2), load_arr(B)
    refs = [a, a2] + ([load_arr(Alate)] if Alate and os.path.exists(Alate) else [])
    sa, sb = blank_stats(a), blank_stats(b)
    noise = max(diff_frac(a, r) for r in refs[1:])
    out = dict(noise_A_vs_A2_and_late=round(noise, 5), A_stats=sa, B_stats=sb)
    thr = max(0.01, 1.5 * noise)
    out["identical_threshold"] = round(thr, 5)

    def judge(x, st):
        d = min(diff_frac(r, x) for r in refs)
        r = dict(diff_frac=round(d, 5))
        a_blank = sa["non_bg_frac"] < 0.0005
        x_blank = st["non_bg_frac"] < 0.0005
        if a_blank:
            r["verdict"] = "a-blank"; r["why"] = "artwork has (almost) no visible ink even with full network"
        elif x_blank:
            r["verdict"] = "broken"; r["why"] = "blank where A is not"
        elif noise > 0.3:
            # the artwork changes by itself so much that pixels cannot be compared: fall back to ink coverage ratio
            ratio = st["non_bg_frac"] / max(sa["non_bg_frac"], 1e-9)
            r["unstable_reference"] = True
            r["verdict"] = "identical" if 0.6 <= ratio <= 1.6 else "degraded"
            r["why"] = f"animated reference (noise {noise:.2f}); judged by ink coverage ratio {ratio:.2f}"
        elif d <= thr:
            r["verdict"] = "identical"
        elif st["non_bg_frac"] < 0.25 * sa["non_bg_frac"]:
            r["verdict"] = "broken"; r["why"] = "most of the artwork missing"
        else:
            r["verdict"] = "degraded"; r["why"] = "pixel difference above noise floor"
        return r
    out["B"] = judge(b, sb)
    if C:
        c = load_arr(C)
        out["C_stats"] = blank_stats(c)
        out["C"] = judge(c, out["C_stats"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--conds", default="A,A2,B,C")
    ap.add_argument("--delay", type=float, default=None)
    ap.add_argument("--viewport", type=int, default=800)
    args = ap.parse_args()
    d = GAL / args.slug
    meta = json.loads((d / "meta.json").read_text())
    art = d / meta["artwork_file"]
    doc_bytes = art.read_bytes()
    doc_type = meta.get("doc_type", "text/html; charset=utf-8")
    delay = args.delay if args.delay is not None else meta.get("delay", 4)
    archive = load_archive()
    from playwright.sync_api import sync_playwright
    res = {"slug": args.slug, "rendered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "viewport": args.viewport, "delay_s": delay,
           "chromium": CHROME}
    runs = {}
    with sync_playwright() as pw:
        for c in args.conds.split(","):
            cond = c[0]
            r = run_condition(pw, cond, doc_bytes, doc_type, archive, args.viewport, delay, d / f"shot_{c}")
            (d / f"requests_{c}.json").write_text(json.dumps(r["log"], indent=1))
            (d / f"console_{c}.json").write_text(json.dumps({"console": r["console"], "pageerrors": r["errors"], "nav_error": r["nav_error"], "dom": r["dom"]}, indent=1))
            ext = [x for x in r["log"] if not x["url"].startswith(BASE) and not x["url"].startswith("data:")]
            runs[c] = dict(n_requests=len(r["log"]), n_external=len(ext), actions={k: sum(1 for x in ext if x.get("action") == k) for k in {x.get("action") for x in ext}},
                           n_console_errors=len(r["console"]), n_page_errors=len(r["errors"]), dom=r["dom"])
    res["runs"] = runs
    if all(os.path.exists(d / f"shot_{k}.png") for k in ("A", "A2", "B")):
        res["metrics"] = verdict(d / "shot_A.png", d / "shot_A2.png", d / "shot_B.png", d / "shot_C.png" if (d / "shot_C.png").exists() else None, d / "shot_A_late.png")
    (d / "result.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "runs"}, indent=1))
    for c, r in runs.items():
        print(c, r["n_external"], r["actions"], "console_err", r["n_console_errors"], "page_err", r["n_page_errors"], r["dom"].get("canvas"), r["dom"].get("svg"))


if __name__ == "__main__":
    main()
