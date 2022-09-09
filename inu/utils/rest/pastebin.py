import urllib.request
import urllib.parse
from core import ConfigProxy, ConfigType, getLogger
import aiohttp  
import asyncio

log = getLogger(__name__)
config = ConfigProxy(ConfigType.YAML)

class PasteBin:
    dev_key = config.pastebin.SECRET
    session: aiohttp.ClientSession = None

    @classmethod
    async def _create_session(cls) -> aiohttp.ClientSession:
        return aiohttp.ClientSession()


    @classmethod
    async def _get_session(cls) -> aiohttp.ClientSession:
        if cls.session is None or cls.session.closed:
            cls.session = await cls._create_session()
        return cls.session

    @classmethod
    async def upload(cls, code: str):
        site = 'https://pastebin.com/api/api_post.php'
        api_paste_private = '1'; # 0=public 1=unlisted 2=private
        api_paste_expire_date = '6M';
        api_paste_format = "python"
        data_bytes = {
                "api_dev_key": cls.dev_key, 
                "api_option": "paste", 
                "api_paste_code": code,
                "api_paste_private": api_paste_private,
                "api_paste_expire_date": api_paste_expire_date,
                "api_paste_format": api_paste_format,
            }
        
        session = await cls._get_session()
        async with session.post(url=site, data=data_bytes) as resp:
            if str(resp.status).startswith("4"):
                print(await resp.text())  
            print(await resp.text())
        await session.close()
            
        # our_data = our_data_bytes.encode()
        # request = urllib.request.Request(site, method='POST')
        # resp = urllib.request.urlopen(request, our_data)
        # print(resp.read())

asyncio.run(PasteBin.upload(str(20000*"A")))
asyncio.run(PasteBin.upload("testfsdlksj"))
asyncio.run(PasteBin.upload("testfsdlksj"))
asyncio.run(PasteBin.upload("testfsdlksj"))
