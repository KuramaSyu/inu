from optparse import Option
from os import stat
from pydoc import _OldStyleClass
from typing import (
    Optional,
    List,
    Union
)

import asyncpg
from asyncache import cached
from cachetools import TTLCache, LRUCache

from .db import Database

class TagManager():
    db = Database()
    
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @classmethod
    async def set(
        cls, 
        key: str, 
        value: str, 
        creator: int,
        check_if_taken: bool = True,
    ):
        await cls._do_check_if_taken(key, check_if_taken)
        await cls.db.execute(
            """
            INSERT INTO tags(tag_key, tag_value, creator)
            VALUES($1, $2, $3)
            """,
            key,
            value,
            creator,
        )

    @classmethod
    async def append(
        cls, 
        key: str,
        value: str,
        log_like: bool = False,
        check_if_taken: bool = False,
    ) -> asyncpg.Record:
        await cls._do_check_if_taken(key, check_if_taken)
        record = await cls.db.row("""SELECT * FROM tags""")
        record["tag_value"].append(value)
        await cls.sync_record(record)
        return record


    @classmethod
    async def remove(cls, key: str, creator: int) -> List[asyncpg.Record]:
        """Remove where arguments are eqaul and return those records"""
        sql = """
            DELETE FROM tags
            WHERE tag_key = $1 AND creator = $2
            RETURNING *
            """
        return await cls.db.fetch(sql, key, creator)


    @classmethod
    async def sync_record(
        cls,
        record: asyncpg.Record,
    ):
        sql = """
            UPDATE tags
            SET tag_value = $1
            WHERE tag_ID = $2
            """
        await cls.db.execute(sql, record["tag_value"], record["tag_ID"])

    @classmethod
    async def is_taken(cls, key, tags: Optional[List[str]] = None):
        if not tags:
            tags = cls.db.column(
                """SELECT * FROM tags""", 
                column="tag_key"
            )
        if key in tags:
            return True
        return False

    @classmethod
    async def _do_check_if_taken(cls, key, b):
        if b:
            is_taken = await cls.is_taken(key)
            if is_taken:
                raise TagIsTakenError

class Tag():
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @cached(TTLCache, 1024, 120)
    async def is_taken(self) -> bool:
        return True

class TagIsTakenError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)