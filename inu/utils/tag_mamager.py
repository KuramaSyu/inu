from typing import (
    Dict,
    Optional,
    List,
    Tuple,
    Union
)
import typing
from copy import deepcopy

import asyncpg
from asyncache import cached
from cachetools import TTLCache, LRUCache
import hikari
from hikari import User, Member
from numpy import column_stack


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
        author: Union[User, Member],
        check_if_taken: bool = True,
    ):
        """
        Creates a db entry for given args.
        Raises:
            TagIsTakenError if tag is taken
        """
        guild_id = author.guild_id if isinstance(author, hikari.Member) else None #type: ignore
        await cls._do_check_if_taken(key, guild_id, check_if_taken)
        await cls.db.execute(
            """
            INSERT INTO tags(tag_key, tag_value, creator_id, guild_id)
            VALUES($1, $2, $3, $4)
            """,
            key,
            [value],
            author.id,
            guild_id,
        )

    @classmethod
    async def edit(
        cls, 
        key: str,
        value: str,
        author: Union[hikari.User, hikari.Member],
        tag_id: int,
        check_if_taken: bool = False,
    ) -> asyncpg.Record:
        """
        Updates a tag by key
        Args:
            key: the key to match for#
            guild_id: the guild id to check for.
            NOTE: if its None it will only check global, otherwise only local
            check: wether the check should be executed or not
        Raises:
            utils.tag_manager.TagIsTakenError: if Tag is taken (wether gobal or local see guild_id)

        """
        sql = """
            SELECT tag_id FROM tags
            WHERE tag_id = $1
            """
        guild_id = author.guild_id if isinstance(author, hikari.Member) else None
        await cls._do_check_if_taken(key, guild_id, check_if_taken)
        record = await cls.db.row(sql, tag_id)
        record["author"] = author.id
        record["tag_value"] = [value]
        record["tag_key"] = key
        record["guild_id"] = guild_id

        await cls.sync_record(record)
        return record


    @classmethod
    async def remove(cls, id: int) -> List[asyncpg.Record]:
        """Remove where id mathes and return all matched records"""
        sql = """
            DELETE FROM tags
            WHERE tag_id = $1
            RETURNING *
            """
        return await cls.db.fetch(sql, id)

    @classmethod
    async def get(
        cls,
        key: str,
        guild_id: Optional[int] = None,
        only_accessable: bool = True
    ) -> List[asyncpg.Record]:
        """
        Returns the tag of the key, or multiple, if overridden in guild.
        This function is a corotine.

        Args:
        -----
        key: (str) the key to search
        - guild_id: (int) [default None] the guild_id the tag should have
            - Note: None is equivilant with `global` tag
        - only_accessable: (bool) wehter or not the function should return only 
            the gobal and/or local one instead of every tag with matching `key`
        """
        sql = """
            SELECT * FROM tags
            WHERE (tag_key = $1) AND (guild_id = $2::BIGINT OR guild_id IS NULL)
            """
        records: Optional[List[asyncpg.Record]] = await cls.db.fetch(sql, key, guild_id)

        if not records:
            return []
        if not only_accessable:
            return records
        filtered_records = []
        for record in records:
            if (
                record["guild_id"] == guild_id
                or record["guild_id"] is None
            ):
                filtered_records.append(record)
        return filtered_records


    @classmethod
    async def sync_record(
        cls,
        record: asyncpg.Record,
    ):
        """
        Updates a record in the db
        Args:
            record: (asyncpg.record) the record which should be updated
            old_record: (asyncpg.Record) the old record, how it is stored in the db
        
        """
        sql = """
            UPDATE tags
            SET (tag_value, tag_key, creator_id, guild_id) = ($1, $2, $3, $4)
            WHERE tag_ID = $5
            """
        await cls.db.execute(
            sql,
            record["tag_value"],
            record["tag_key"],
            record["creator_id"],
            record["guild_id"],
            record["tag_ID"],
        )

    @classmethod
    async def is_global_taken(cls, key, tags: Optional[List[str]] = None):
        """
        Args:
            key: the key to search
            tags: an already fetched column (list) of all tags
        Raises:
            utils.tag_manager.TagIsTakenError
        """
        sql = """
            SELECT tags, guild_id FROM tags
            WHERE tags = $1
            """
        if not tags:
            tags = await cls.db.column(
                sql,
                column="tag_key",
            )
        if key in tags:
            return True
        return False

    @classmethod
    async def is_taken(cls, key, guild_id: Optional[int]) -> Tuple[bool, bool]:
        """
        Args:
            key: the key to search
            guild_id: the guild if to check for.
            NOTE: if its None it will only check global, otherwise only local

        Returns:
            bool: is local taken
            bool: is global taken
        """
        sql = """
            SELECT tags FROM tags
            WHERE tag_key = $1
            """
        if guild_id is None:
            guild_id = 0
        records = await cls.db.column(sql, key, column="tags")
        if len(records) == 0:
            return False, False

        global_taken = False
        local_taken = False
        for record in records:
            if record["guild_id"] == guild_id:
                local_taken = True
            elif record["guild_id"] is None:
                global_taken = True
            if global_taken and local_taken:
                return True, True

        return local_taken, global_taken      
    
    @classmethod
    async def _do_check_if_taken(cls, key: str, guild_id: Optional[int], check: bool = True):
        """
        Tests if a tag is taken by key.
        Args:
            key: the key to match for#
            guild_id: the guild if to check for.
            NOTE: if its None it will only check global, otherwise only local
            check: wether the check should be executed or not
        Raises:
            utils.tag_manager.TagIsTakenError: if Tag is taken (wether gobal or local see guild_id)
        """
        if not check:
            return
        local_taken, global_taken = await cls.is_taken(key, guild_id)
        if local_taken and global_taken:
            raise TagIsTakenError(f"Tag `{key}` is global and local taken")
        if global_taken and guild_id is None:
            raise TagIsTakenError(f"Tag `{key}` is global taken")
        if local_taken and guild_id is not None:
            raise TagIsTakenError(f"Tag `{key}` is local taken")

class Tag():
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @cached(TTLCache, 1024, 120)
    async def is_taken(self) -> bool:
        return True

class TagIsTakenError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)