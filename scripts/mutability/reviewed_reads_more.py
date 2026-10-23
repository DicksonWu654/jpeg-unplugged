"""Additional named data paths and claimant tokenURIs absent from the census."""
import json,pathlib,sys
import pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/mutability'))
from reviewed_reads_cases import read
import reviewed_reads_read as R


def main():
    # Correct ABI uses uint32 for scale factor; retain failed selector probe for audit.
    mb='0xb1befc9e7b76c1e846ebbf3e6e1ab029c86e7435'
    read(mb,'artworkURI(uint256,uint32)',(1,15),('uint256','uint32'))
    read(mb,'artworkPixels(uint256)',(1,),('uint256',),('bytes',))
    cr='0x78f51427020c5ba128b07e99325d71250b0ed0e1'
    read(cr,'onChainTokenURI(uint256)',(1,),('uint256',))
    oncr='0xfdac77881ff861ff76a83cc43a1be3c317c6a1cc'
    R.save(oncr+'_source','https://eth.blockscout.com/api/v2/smart-contracts/'+oncr,'GET')
    R.rpc('cryptoskulls_data_owner_code','eth_getCode',['0x9af756e7be065dca83674ec17f3703579a544da1',R.block()])
    moon='0x60cd862c9c687a9de49aecdc3a99b74a4fc54ab6'
    read(moon,'getCatDetails(bytes5)',(bytes.fromhex('000f53c2fd'),),('bytes5',),('bytes5','address','bytes32','address','uint256','address','uint256'))
    for a in ['0x059edd72cd353df5106d2b9cc5ab83a52287ac3a','0xa7d8d9ef8d8ce8992df33d8b8cf4aebabd5bd270']:
        read(a,'projectScriptByIndex(uint256,uint256)',(0,0),('uint256','uint256'))
        read(a,'tokenIdToHash(uint256)',(0,),('uint256',),('bytes32',))
    for i in [0,1,2,3]:
        tx=read('0x8754f54074400ce745a7ceddc928fb1b7e985ed6','getScriptAtIndex(uint256)',(i,),('uint256',))
        if isinstance(tx,str):
            result=R.rpc('euler_script_tx_'+tx,'eth_getTransactionByHash',[tx])
            if not (result or {}).get('result'):
                R.save('euler_script_bs_'+tx,'https://eth.blockscout.com/api/v2/transactions/'+tx,'GET')
    # Claimants outside the census are still scored; a failed sample read remains unverifiable.
    v=pd.read_csv(ROOT/'data/claims/claimants_reviewed.csv')
    f=pd.read_parquet(ROOT/'data/analysis/collections_enriched.parquet')
    m=pd.read_csv(ROOT/'data/mutability/mutability.csv').set_index('address')
    g=pd.read_csv(ROOT/'data/gallery/results.csv');ids=dict(zip(g.contract.str.lower(),g.token))
    rows=[]
    for a in sorted(set(v.address)-set(f.a)):
        token=int(ids.get(a,1));std=m.loc[a,'standard'];sig='uri(uint256)' if std=='ERC-1155' else 'tokenURI(uint256)'
        result=read(a,sig,(token,),('uint256',),key=a+'_reviewed_tokenuri')
        rows.append({'address':a,'token_id':token,'signature':sig,'uri_head':result[:160] if isinstance(result,str) else None,'raw_path':f'data/mutability/reviewed_reads/{a}_reviewed_tokenuri.json'})
        (R.OUT/'claimant_tokenuris.json').write_text(json.dumps(rows,indent=1)+'\n')


if __name__=='__main__':main()
