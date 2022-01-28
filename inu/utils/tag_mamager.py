from typing import (
    Dict,
    Optional,
    List,
    Tuple,
    Union,
    Mapping,
    Any
)
import typing
from copy import deepcopy
from enum import Enum

import asyncpg
from asyncache import cached
from cachetools import TTLCache, LRUCache
import hikari
from hikari import User, Member
from numpy import column_stack


from core.db import Database


class TagType(Enum):
    YOUR = 1
    GUILD = 2
    GLOBAL = 3

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
        guild_id: Optional[int] = None,
        check_if_taken: bool = True,
    ) -> int:
        """
        Creates a db entry for given args.

        Args
        -----
            - key: (str) the tag name
            - value: (str) the tag value
            - author: (User | Member) the user who created the tag
            - guild_id: (int | None, default=None) the guild_id if the tag should be local;
            to make a tag global set guild_id to None
            - check_if_taken: (bool, default=True) check if the tag is already taken

        Returns
        -------
            - (int) the tag_id of the stored tag
        Raises
        -------
            - TagIsTakenError if tag is taken
        """
        #guild_id = author.guild_id if isinstance(author, hikari.Member) else None #type: ignore
        await cls._do_check_if_taken(key, guild_id, check_if_taken)
        record = await cls.db.row(
            """
            INSERT INTO tags(tag_key, tag_value, creator_id, guild_id)
            VALUES($1, $2, $3, $4)
            RETURNING tag_id
            """,
            key,
            [value],
            author.id,
            guild_id,
        )
        return record["tag_id"]

    @classmethod
    async def edit(
        cls, 
        key: str,
        value: str,
        author: Union[hikari.User, hikari.Member],
        tag_id: int,
        guild_id: Optional[int] = None,
        check_if_taken: bool = False,
    ) -> Mapping[str, Any]:
        """
        Updates a tag by key
        Args:
        -----
            - key: (str) the name which the tag should have
            - value: (str) the value of the tag
            - guild_id: (int | None, default=None) the guild id to check for. None=global
            NOTE: if its None it will only check global, otherwise only local
            - check_if_taken: wether the check should be executed or not

        Raises:
        -------
            - utils.tag_manager.TagIsTakenError: if Tag is taken (wether gobal or local see guild_id)

        """
        def correct_value(value) -> List[str]: #type: ignore
            if isinstance(value, str):
                return [value]
            elif isinstance(value, list):
                if isinstance(value[0], list):
                    correct_value(value[0])
                else:
                    return value
            else:
                raise TypeError
        sql = """
            SELECT * FROM tags
            WHERE tag_id = $1
            """
        # guild_id = author.guild_id if isinstance(author, hikari.Member) else None
        await cls._do_check_if_taken(key, guild_id, check_if_taken)
        record = await cls.db.row(sql, tag_id)
        new_record = {
            "creator_id": author.id,
            "tag_value": correct_value(value),  # is already in a list
            "tag_key": key,
            "guild_id": guild_id,
            "tag_ID": record["tag_id"]
        }

        await cls.sync_record(new_record)
        return record


    @classmethod
    async def remove(cls, id: int) -> List[Mapping[str, Any]]:
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
    ) -> List[Mapping[str, Any]]:
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
        records: Optional[List[Mapping[str, Any]]] = await cls.db.fetch(sql, key, guild_id)

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
        record: Mapping[str, Any],
    ):
        """
        Updates a record in the db
        Args:
            record: (Mapping[str, Any]) the record which should be updated
            old_record: (Mapping[str, Any]) the old record, how it is stored in the db
        
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
    
    @classmethod
    async def get_tags(cls, type: TagType, guild_id: Optional[int], author_id: Optional[int]) -> Optional[asyncpg.Record]:
        sql = """
            SELECT * FROM tags
            """
        if type == TagType.GLOBAL:
            sql = f"{sql} WHERE guild_id IS NULL"
            return await cls.db.fetch(sql)
        elif type == TagType.GUILD:
            if guild_id is None:
                raise RuntimeError("Can't fetch tags of a guild without an id (id is None)")
            sql = f"{sql} WHERE guild_id = $1"
            return await cls.db.fetch(sql, guild_id)
        elif type == TagType.YOUR:
            if author_id is None:
                raise RuntimeError("Can't fetch tags of a creator without an id (id is None)")
            sql = f"{sql} WHERE creator_id = $1"
            return await cls.db.fetch(sql, author_id)
        

class Tag():
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @cached(TTLCache, 1024, 120)
    async def is_taken(self) -> bool:
        return True

class TagIsTakenError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)