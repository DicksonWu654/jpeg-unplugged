#!/usr/bin/env python3
"""Write site/data/available.json: which optional datasets exist. Run after any build script (they call it too)."""
import json, os
SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(SITE, "data")
out = {k: os.path.exists(os.path.join(D, k + ".json")) for k in ("mutability", "hosts", "collections_extra")}
json.dump(out, open(os.path.join(D, "available.json"), "w"))
print("available.json", out)
if __name__ == "__main__":
    pass
