import socket
import traceback

import aiohttp

from core import getLogger


log = getLogger(__name__)


class IP:
    @classmethod
    async def fetch_public_ip(cls, ssl: bool = True, timeout: int = 4) -> str:
        """Returns the public IP"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.ipify.org?format=json", ssl=ssl, timeout=timeout) as resp:
                    data = await resp.json()
                    return data["ip"]
        except Exception:
            if ssl:
                return await cls.fetch_public_ip(ssl=False, timeout=2)
            else:
                log.warning(traceback.format_exc())
                return "Unknown"

    @staticmethod
    def get_private_ip() -> str:
        """Returns the private IP"""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP