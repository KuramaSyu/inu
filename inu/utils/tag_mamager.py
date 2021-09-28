from typing import (
    Optional,
    List,
    Union
)
import typing

import asyncpg
from asyncache import cached
from cachetools import TTLCache, LRUCache
from hikari import User

from .db import Database

class TagManager():
    db: Database
    
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @classmethod
    def set_db(cls, database: Database):
        cls.db = database

    @classmethod
    async def set(
        cls, 
        key: str, 
        value: str, 
        creator_id: int,
        check_if_taken: bool = True,
    ):
        """
        Creates a db entry for given args.
        :Raises:
        TagIsTakenError if tag is taken
        """
        await cls._do_check_if_taken(key, check_if_taken)
        await cls.db.execute(
            """
            INSERT INTO tags(tag_key, tag_value, creator)
            VALUES($1, $2, $3)
            """,
            key,
            value,
            creator_id,
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
    async def remove(cls, key: str, creator: User) -> List[asyncpg.Record]:
        """Remove where arguments are eqaul and return those records"""
        sql = """
            DELETE FROM tags
            WHERE tag_key = $1 AND creator_id = $2
            RETURNING *
            """
        return await cls.db.fetch(sql, key, creator.id)

    @classmethod
    async def get(cls, key: str, guild_id: int = 0) -> List[asyncpg.Record]:
        """Returns the tag of the key, or multiple, if overridden in guild"""
        sql = """
            SELECT * FROM tags
            WHERE tag_key = $1 AND (guild_id = $2 OR guild_id IS NULL)
            """
        return await cls.db.fetch(sql, key, guild_id)

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