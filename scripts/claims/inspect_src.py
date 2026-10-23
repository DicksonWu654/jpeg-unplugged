"""Print tokenURI function bodies + http(s)/ipfs literals + URI setters for an address (manual red-flag verification)."""
import re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import srcscan as S
for a in sys.argv[1:]:
    a = a.lower(); rec = S.load(a)
    if not rec: print(a, "NO SRC"); continue
    files = S.files_of(rec)
    impl = (rec.get("Implementation") or "").lower()
    if impl and S.have(impl): files += S.files_of(S.load(impl))
    print("=" * 100); print(a, rec.get("ContractName"), rec.get("CompilerVersion"), "proxy" if impl else "")
    for fn, t in files:
        if S.LIB.search(fn) and "openzeppelin" in fn.lower(): continue
        for m in re.finditer(r"function\s+tokenURI\s*\([^)]*\)[^{;]*\{", t):
            body = t[m.start():m.start() + 700]
            print(f"--- {fn}: {body[:700]}")
        for m in re.finditer(r"[\"'](https?://[^\"']{0,100}|ipfs://[^\"']{0,80}|ar://[^\"']{0,60})", t):
            print("   literal:", m.group(0)[:130], "|", fn[-30:])
        for m in re.finditer(S.SET_URI, t, re.I): print("   setter:", m.group(1), "|", fn[-30:])
