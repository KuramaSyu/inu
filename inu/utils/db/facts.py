import asyncpg
from typing import * 
import asyncio
import hashlib

from utils import RESTFacts
from core import Table

class Facts:
    _table = Table("facts", debug_log=False, error_log=False)
    last_metrics = {"from": 0, "unique": 0}

    @classmethod
    async def add_fact(cls, fact: str) -> bool:
        """add fact to db"""
        hs = hashlib.sha256(fact.encode("utf-8")).hexdigest() 
        try:
            await cls._table.insert(["type", "fact", "sha256"], ["basic", fact, hs], on_conflict="DO NOTHING")
        except Exception:
            return False
        return True

    @classmethod
    async def fetch_random_fact(cls) -> str | None:
        """fetch random fact from db"""
        try:
            records = await cls._table.fetch(f"SELECT * FROM {cls._table.name} ORDER BY random() limit 1;")
            return records[0]["fact"]
        except Exception:
            return None

    @classmethod
    async def _cache_resp(cls, resp: List[Dict[str, str]]) -> None:
        """cache RSET resp to db"""
        tasks = [asyncio.create_task(Facts.add_fact(entry["fact"])) for entry in resp]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
        sum_ = 0
        for d in done:
            if d.result():
                sum_ += 1
        cls.last_metrics = {"from": len(resp), "unique": sum_}
            

    @classmethod
    async def _fetch_from_rest(cls, amount: int = 30) -> int:
        """fetch REST resp and cache it. 
        
        Args:
        -----
        amount : int
            the amount of facts from 0 - 30
        """
        resp = await RESTFacts.fetch_facts(amount=amount)
        asyncio.create_task(cls._cache_resp(resp))
        return resp