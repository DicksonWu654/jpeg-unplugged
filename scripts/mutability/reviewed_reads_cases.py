"""Read-only calls for separate-data-contract fairness and the S13 control paths."""
import json,pathlib,re,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/mutability'))
sys.path.insert(0,str(ROOT/'scripts/claims'))
import reviewed_reads_read as R
import srcscan
from eth_abi import decode


def read(a,sig,args=(),types=(),out=('string',),key=None):
    r=R.call(a,sig,args,types,key=key)
    if r and 'result' in r:
        try:
            val=decode(out,bytes.fromhex(r['result'][2:]))
            print(a,sig,args,str(val)[:240],flush=True)
            return val[0] if len(val)==1 else val
        except Exception as e:print(a,sig,'decode error',str(e),flush=True)
    else:print(a,sig,args,r,flush=True)


def main():
    skull='0x9a7b94954751d539c63e16aa6e0557c451251394'
    read(skull,'owner()',out=('address',))
    R.rpc('cryptoskulls_data_code','eth_getCode',[skull,R.block()])
    for token in [0,1,9999]:
        read(skull,'getAttrs(uint16)',(token,),('uint16',),('uint8[]',))
        read(skull,'getName(uint16)',(token,),('uint16',))
        read(skull,'getPixels(uint16)',(token,),('uint16',),('uint24[]',))
        read(skull,'getSvg(uint16)',(token,),('uint16',))
    read('0x8d04a8c79ceb0889bdd12acdf3fa9d207ed3ff63','tokenSvgDataOf(uint256)',(1,),('uint256',))
    read('0x8d04a8c79ceb0889bdd12acdf3fa9d207ed3ff63','tokenDataOf(uint256)',(1,),('uint256',),('bytes',))
    read('0x91047abf3cab8da5a9515c8750ab33b4f1560a7a','getFace(uint256)',(1,),('uint256',))
    read('0x91047abf3cab8da5a9515c8750ab33b4f1560a7a','getGolfScore(uint256)',(1,),('uint256',),('uint256',))
    moon='0x60cd862c9c687a9de49aecdc3a99b74a4fc54ab6'
    R.save(moon+'_source','https://eth.blockscout.com/api/v2/smart-contracts/'+moon,'GET')
    cat=read(moon,'rescueOrder(uint256)',(1,),('uint256',),('bytes5',))
    if cat:read(moon,'getCatDetails(bytes5)',(cat,),('bytes5',),('bytes5','address','bytes32','address','uint256','address','uint256'))
    mb='0x23581767a106ae21c074b2276d25e5c3e136a68b'
    read(mb,'owner()',out=('address',))
    safe='0x80d154d71f2e1400311c539ef5d08710bd37d044'
    read(safe,'getThreshold()',out=('uint256',));read(safe,'getOwners()',out=('address[]',))
    renderer=read(mb,'renderingContract()',out=('address',))
    if renderer:
        owner=read(renderer,'owner()',out=('address',))
        if owner:R.rpc('moonbirds_renderer_owner_code','eth_getCode',[owner,R.block()])
        legacy=read(renderer,'legacyRenderer()',out=('address',))
        read(renderer,'baseUri()');read(renderer,'animationBaseUri()')
        read(renderer,'useNewArtwork(uint256)',(1,),('uint256',),('bool',))
        read(renderer,'artworkUri(uint256)',(1,),('uint256',))
        if legacy:
            R.save(legacy+'_source','https://eth.blockscout.com/api/v2/smart-contracts/'+legacy,'GET')
            read(legacy,'artworkURI(uint256,uint32)',(1,15),('uint256','uint32'))
    cr='0x97597002980134bea46250aa0510c9b90d87a587'
    rend=read(cr,'renderingContractAddress()',out=('address',))
    if rend:
        R.save(rend+'_source','https://eth.blockscout.com/api/v2/smart-contracts/'+rend,'GET')
        read(rend,'onChainRenderer()',out=('address',))
    read(cr,'getDna(uint256)',(1,),('uint256',),('uint256',))
    cb='0x892848074ddea461a15f337250da3ce55580ca85'
    read(cb,'render(uint256)',(1,),('uint256',))
    euler='0x8754f54074400ce745a7ceddc928fb1b7e985ed6'
    read(euler,'scriptCount()',out=('uint256',))
    read(euler,'getScriptAtIndex(uint256)',(0,),('uint256',))
    av='0xf3e778f839934fc819cfa1040aabacecba01e049'
    read(av,'renderAvastar(uint256)',(1,),('uint256',))
    for a in ['0xc1caf0c19a8ac28c41fe59ba6c754e4b9bd54de9','0x8d04a8c79ceb0889bdd12acdf3fa9d207ed3ff63','0x91047abf3cab8da5a9515c8750ab33b4f1560a7a','0xc3f733ca98e0dad0386979eb96fb1722a1a05e69',mb,cr,cb]:
        read(a,'tokenURI(uint256)',(1,),('uint256',))


if __name__=='__main__':main()
