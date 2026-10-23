"""Exhaustive read-only CryptoSkulls coverage using a small eth_call view lens.

The lens exists only in eth_call's code override at 0x...cafe; it issues STATICCALLs and
returns a count plus a rolling digest. It is never deployed or sent as a transaction.
Each saved request includes the complete code and exact block. No storage is overridden.
"""
import json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/mutability'))
import reviewed_reads_read as R
from keccak import selector
ADDRESS='0x9a7b94954751d539c63e16aa6e0557c451251394'
LENS='0x000000000000000000000000000000000000cafe'


def lens(start,end,sig,length):
    code=bytearray();labels={};refs=[]
    def op(*bs):code.extend(bs)
    def push(n):
        b=n.to_bytes(max(1,(n.bit_length()+7)//8),'big');op(0x5f+len(b));code.extend(b)
    def jump(label,conditional=False):
        op(0x61);refs.append((len(code),label));op(0,0,0x57 if conditional else 0x56)
    # memory: index=0; valid count=32; rolling hash=64; calldata=96; return=160.
    push(start);push(0);op(0x52)
    push(int(selector(sig),16)<<224);push(96);op(0x52)
    labels['loop']=len(code);op(0x5b)
    push(0);op(0x51);push(100);op(0x52)
    # staticcall(gas(), ADDRESS, 96, 36, 160, size)
    size=64+32*length
    push(size);push(160);push(36);push(96);push(int(ADDRESS,16));op(0x5a,0xfa)
    # AND success with exact return size and array length.
    op(0x3d);push(size);op(0x14,0x16)
    push(192);op(0x51);push(length);op(0x14,0x16)
    push(32);op(0x51,0x01);push(32);op(0x52)
    # hash every raw returned byte then chain to previous hash; memory below calldata.
    push(size);push(160);op(0x20);push(128);op(0x52)
    push(64);op(0x51);push(96);op(0x52)
    push(64);push(96);op(0x20);push(64);op(0x52)
    # restore selector overwritten by hash buffer
    push(int(selector(sig),16)<<224);push(96);op(0x52)
    push(0);op(0x51);push(1);op(0x01);op(0x80);push(0);op(0x52)
    push(end);op(0x14);jump('done',True);jump('loop')
    labels['done']=len(code);op(0x5b);push(64);push(32);op(0xf3)
    for off,label in refs:code[off:off+2]=labels[label].to_bytes(2,'big')
    return '0x'+code.hex()


def main():
    summary={'block':R.block(),'contract':ADDRESS,'lens_address':LENS,'method':'eth_call code override; STATICCALL only; count validates success, ABI return size and array length','ranges':[]}
    # Both methods for all 10,000 IDs; compact raw evidence includes every input and digest.
    for sig,length,step in [('getAttrs(uint16)',10,500),('getPixels(uint16)',576,50)]:
        total=0
        for start in range(0,10000,step):
            end=min(10000,start+step);key=f'coverage_{sig.split("(")[0]}_{start:04d}_{end:05d}'
            params=[{'to':LENS,'gas':hex(150_000_000)},R.block(),{LENS:{'code':lens(start,end,sig,length)}}]
            r=R.rpc(key,'eth_call',params)
            if not r or 'result' not in r:
                print(key,'FAILED',r,flush=True);break
            raw=bytes.fromhex(r['result'][2:]);n=int.from_bytes(raw[:32],'big');total+=n
            summary['ranges'].append({'signature':sig,'start':start,'end_exclusive':end,'valid':n,'digest':'0x'+raw[32:64].hex(),'raw_path':f'data/mutability/reviewed_reads/{key}.json'})
            (R.OUT/'cryptoskulls_coverage.json').write_text(json.dumps(summary,indent=1)+'\n')
            print(key,n,'/',end-start,'running',total,flush=True)
            if n!=end-start:raise RuntimeError('coverage mismatch')
        print(sig,'TOTAL',total,flush=True)


def control():
    """Validate the lens digest against direct reads at a fresh pinned block."""
    fresh=R.rpc('coverage_control_block','eth_blockNumber',[])['result']
    for sig,length in [('getAttrs(uint16)',10),('getPixels(uint16)',576)]:
        stem=sig.split('(')[0]
        R.rpc('coverage_control_fresh_'+stem,'eth_call',[
            {'to':LENS,'gas':hex(50_000_000)},fresh,
            {LENS:{'code':lens(1,2,sig,length)}}])
        R.call(ADDRESS,sig,(1,),('uint16',),key='coverage_control_direct_'+stem,block_tag=fresh)


if __name__=='__main__':
    control() if '--control' in sys.argv else main()
