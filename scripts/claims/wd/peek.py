import sys; sys.path.insert(0,'scripts/claims'); import wd_common as C
for key in sys.argv[1:]:
    raw=open(f'data/raw/claims-web/{key}.html',errors='replace').read()
    seen=set(); print('=====',key)
    for c in C.html_candidates(raw):
        for s in C.sentences(c):
            if s in seen or not C.strength(s) or not C.clean_ok(s): continue
            seen.add(s); print(' -',C.strength(s),'|',s[:300])
