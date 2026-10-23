import json, time, sys
import chain, srcflags
rows=[json.loads(l) for l in open(chain.GAL/'discovery/classified.jsonl')]
out=chain.GAL/'discovery/srcflags.jsonl'
done={json.loads(l)['address'] for l in open(out)} if out.exists() else set()
with open(out,'a') as f:
    for r in rows:
        if r['address'] in done: continue
        try: fl=srcflags.flags(r['address'])
        except Exception as e: fl={'error':str(e)[:100]}
        f.write(json.dumps(dict(address=r['address'],name=r['name'],flags=fl))+'\n'); f.flush(); time.sleep(0.3)
