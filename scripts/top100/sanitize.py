"""Sanitize only this study area's new artifacts before release."""
import json
from common import ROOT,OUT,write
from build import clean,REDACTOR


def main():
    for p in sorted(OUT.rglob('*')):
        if not p.is_file():continue
        if p.suffix=='.json':write(p,clean(json.loads(p.read_text())))
        elif p.suffix in ('.log','.md'):
            p.write_text(clean(p.read_text()))
    for p in [ROOT/'docs/methods/top100.md',ROOT/'site/data/top100.json']:
        if p.suffix=='.json':write(p,clean(json.loads(p.read_text())))
        else:p.write_text(clean(p.read_text()))
    print('Top-100 artifacts sanitized; validation scans source, CSV, nested values and encoded text separately.')


if __name__=='__main__':main()
