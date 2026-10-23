"""Read alternate on-chain art/data routes discovered during quote review."""
import json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/mutability'))
import reviewed_reads_read as R
from reviewed_reads_cases import read


def main():
    origin=read('0x050dc61dfb867e0fe3cf2948362b6c0f3faf790b','_pixelmapAddress()',out=('address',))
    if origin:
        j=R.save(origin+'_source','https://eth.blockscout.com/api/v2/smart-contracts/'+origin,'GET')['response'] or {}
        print('pixelmap views',[(x.get('name'),x.get('inputs'),x.get('outputs')) for x in j.get('abi',[]) if x.get('type')=='function' and x.get('constant')],flush=True)
        read(origin,'getTile(uint16)',(1,),('uint16',),('string','string','uint256','address'))
    read('0x290841ba121462f90ea527849bd5302c50b6afb5','GENERATOR_SCRIPT_CODE(uint256)',(0,),('uint256',))
    read('0x6c7c97caff156473f6c9836522ae6e1d6448abe7','tokenScript(uint256)',(1,),('uint256',))
    cb='0xec3e38e536ad4fa55a378b14b257976148b618ac'
    read(cb,'renderBroker(uint256,uint256)',(1,0),('uint256','uint256'))
    read(cb,'_renderBroker(uint256,uint256,uint256)',(1,0,400),('uint256','uint256','uint256'))
    read(cb,'getTokenData(uint256)',(1,),('uint256',),('bytes',))


if __name__=='__main__':main()
