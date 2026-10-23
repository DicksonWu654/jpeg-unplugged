import json,sys
for a in sys.argv[1:]:
    e=json.load(open(f'data/mutability/evidence/{a}.json'))
    print(a, e.get('contract_name'), '|', e['class_direct'], e.get('class_deps'), e['class_final'], '|', e['class_reason'][:200])
    print(' proxy', e.get('proxy',{}).get('kind'), 'owner', e.get('owner') and (e['owner']['type'], e['owner']['addr']), 'locks', e.get('lock_views'), 'lockfns', e.get('lock_functions'))
    for m in e.get('mutators',[]): print('  ', m['category'], m['name'], m.get('gates'), 'eff=',m.get('effective'), 'frozen=',m.get('frozen'), [h['desc'] for h in m['holders']], m['holder_how'])
    print(' deps', [(d['address'], d['via'], d['analysis'].get('class_direct')) for d in e.get('dependencies',[])])
    h=e.get('history',{}); print(' hist txs', [(t.get('method'),t.get('timestamp','')[:10]) for t in h.get('txs',[])][:12], {k:v for k,v in h.get('events',{}).items() if v.get('n')})
    for d in h.get('decoded',[])[:6]: print('   dec', d['timestamp'][:10], d['method'], [(p['name'],p['value'][:70]) for p in d['params']])
