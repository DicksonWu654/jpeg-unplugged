#!/bin/sh
# Set the absolute social-image URL, including a deployment subpath if needed.
set -eu
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <https://host/deployment-path>" >&2
  exit 2
fi
build_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$build_dir/../../.venv/bin/python" - "$build_dir/../index.html" "$1" <<'PY'
import pathlib
import sys
from urllib.parse import urlsplit

path, base = pathlib.Path(sys.argv[1]), sys.argv[2].rstrip("/")
url = urlsplit(base)
if (url.scheme not in {"http", "https"} or not url.netloc or url.username
        or url.password or url.query or url.fragment
        or any(c.isspace() or c in '<>"\'' for c in base)):
    sys.exit("Use an absolute http(s) site URL without credentials, query or fragment.")
text = path.read_text()
if text.count("__SITE_URL__") != 2:
    sys.exit("Expected two __SITE_URL__ tokens in index.html; restore the template before setting a new URL.")
path.write_text(text.replace("__SITE_URL__", base))
print("Set OG and Twitter image URLs to " + base + "/og.png")
PY
