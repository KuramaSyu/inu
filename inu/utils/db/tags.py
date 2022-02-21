from threading import local
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
from hikari import Snowflake, User, Member
from numpy import column_stack


from core.db import Database
from core import Inu


class TagType(Enum):
    YOUR = 1
    GUILD = 2
    GLOBAL = 3
    ALL = 4  # all tags the user can see

class TagManager():
    db: Database
    
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @classmethod
    def init_db(cls, bot: Inu):
        cls.db = bot.db
        cls.bot = bot


    @classmethod
    async def set(
        cls, 
        key: str,
        value: str,
        author_ids: List[int],
        guild_ids: List[int],
        aliases: List[str],
        check_if_taken: bool = True,
    ) -> int:
        """
        Creates a db entry for given args.

        Args
        -----
            - key: (str) the tag name
            - value: (str) the tag value
            - author: (User | Member) the user who created the tag
            - guild_id: (int) the guild_id if the tag should be local;
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
        if 0 in guild_ids:
            # when a local tag changes scope to global, the guilds wont be deleted
            # hence, the check would fail, since these are still in
            guild_ids = [0]
        for guild_id in guild_ids:
            await cls._do_check_if_taken(key, guild_id, check_if_taken)
        record = await cls.db.row(
            """
            INSERT INTO tags(tag_key, tag_value, author_ids, guild_ids, aliases)
            VALUES($1, $2, $3, $4, $5)
            RETURNING tag_id
            """,
            key,
            value,
            author_ids,
            guild_ids,
            aliases,
        )
        return record["tag_id"]

    @classmethod
    async def edit(
        cls, 
        key: str,
        tag_id: int,
        value: Optional[str] = None,
        author_ids: Optional[List[int]] = None,
        guild_ids: Optional[List[Union[int, None]]] = None,
        check_if_taken: bool = False,
        aliases: Optional[List[str]] = None,
    ) -> Mapping[str, Any]:
        """
        Updates a tag by key
        Args:
        -----
            - key: (str) the name which the tag should have
            - value: (str) the value of the tag
            - guild_id: (int) the guild id to check for. 0=global
            NOTE: if its 0 it will only check global, otherwise only local
            - check_if_taken: wether the check should be executed or not

        Raises:
        -------
            - utils.tag_manager.TagIsTakenError: if Tag is taken (wether gobal or local see guild_id)

        """
        sql = """
            SELECT * FROM tags
            WHERE tag_id = $1
            """
        # guild_id = author.guild_id if isinstance(author, hikari.Member) else None
        for guild_id in guild_ids:
            await cls._do_check_if_taken(key, guild_id, check_if_taken)
        record = await cls.db.row(sql, tag_id)
        new_record = {k: v for k, v in record.items()}
        if value:
            new_record["tag_value"] = value
        if author_ids:
            new_record["author_ids"] = author_ids
        if guild_ids:
            new_record["guild_ids"] = guild_ids
        if aliases:
            new_record["aliases"] = aliases
        await cls.sync_record(new_record)
        return new_record


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
        guild_id: Optional[int] = 0,
        author_id: Optional[int] = 0,
        only_accessable: bool = True
    ) -> List[Mapping[str, Any]]:
        """
        Returns the tag of the key, or multiple, if overridden in guild.
        This function is a corotine.

        Args:
        -----
        key: (str) the key to search
        - guild_id: (int) [default None] the guild_id the tag should have
            - Note: 0 is equivilant with `global` tag
        - only_accessable: (bool) wehter or not the function should return only 
            the gobal and/or local one instead of every tag with matching `key`
        """
        sql = f"""
            SELECT * FROM tags
            WHERE (tag_key = $1 OR $1 = ANY(aliases)) 
            AND (
                ($2::BIGINT = ANY(guild_ids) OR 0 = ANY(guild_ids)) 
                OR $3 = ANY(author_ids)
                )
            """
        records: Optional[List[Mapping[str, Any]]] = await cls.db.fetch(sql, key, guild_id, author_id)
        return records
        # if not records:
        #     return []
        # if not only_accessable:
        #     return records
        # filtered_records = []
        # for record in records:
        #     if (
        #         guild_id in record["guild_ids"]
        #         or None in record["guild_ids"]
        #     ):
        #         filtered_records.append(record)
        # return filtered_records


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
            SET (tag_value, tag_key, author_ids, guild_ids, aliases) = ($1, $2, $3, $4, $5)
            WHERE tag_id = $6
            """
        await cls.db.execute(
            sql,
            record["tag_value"],
            record["tag_key"],
            record["author_ids"],
            record["guild_ids"],
            record["aliases"],
            record["tag_id"],
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
            SELECT guild_ids FROM tags
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
    async def is_taken(cls, key, guild_ids: Union[List[int], int]) -> Tuple[bool, bool]:
        if isinstance(guild_ids, int):
            guild_ids = [guild_ids]
        local_taken = False
        global_taken = False
        for guild_id in guild_ids:
            local_taken_, global_taken_ = await cls.single_is_taken(key, guild_id)
            if local_taken_:
                local_taken = True
            if global_taken_:
                global_taken = True
        return local_taken, global_taken

    @classmethod
    async def single_is_taken(cls, key, guild_id: Optional[int]) -> Tuple[bool, bool]:
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
            SELECT * FROM tags
            WHERE tag_key = $1 OR $1 = ANY(aliases)
            """
        if guild_id is None:
            guild_id = 0
        records = await cls.db.fetch(sql, key)
        if len(records) == 0:
            return False, False

        global_taken = False
        local_taken = False
        for record in records:
            if  guild_id in record["guild_ids"]:
                local_taken = True
            elif None in record["guild_ids"]:
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
            NOTE: if its 0 it will only check global, otherwise only local
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
            sql = f"{sql} WHERE 0 = ANY(guild_ids)"
            return await cls.db.fetch(sql)
        elif type == TagType.GUILD:
            if guild_id is None:
                raise RuntimeError("Can't fetch tags of a guild without an id (id is None)")
            sql = f"{sql} WHERE $1 = ANY(guild_ids)"
            return await cls.db.fetch(sql, guild_id)
        elif type == TagType.YOUR:
            if author_id is None:
                raise RuntimeError("Can't fetch tags of a creator without an id (id is None)")
            sql = f"{sql} WHERE $1 = ANY(author_ids)"
            return await cls.db.fetch(sql, author_id)
        elif type == TagType.ALL:
            sql = f"{sql} WHERE $1 = ANY(author_ids) OR $2 = ANY(guild_ids) OR 0 = ANY(guild_ids)"
            return await cls.db.fetch(sql, author_id, guild_id)
    
    @classmethod
    async def find_similar(
        cls,
        tag_name: str, 
        guild_id: Optional[int], 
        creator_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        ### searches similar tags to <`tag_name`> in every reachable scope

        Args:
        -----
            - tag_name (`str`) the name of the tag, to search
            - guild_id (`int`) the guild_id, which the returning tags should have
            - creator_id (`int` | None) the creator_id, which the returning tags should have

        Note:
        -----
            - global tags will shown always (guild_id is 0)
            - if creator_id is None, the creator will be ignored
        """
        cols = ["guild_ids"]
        vals = [guild_id]
        if creator_id:
            cols.append("author_ids")
            vals.append(creator_id)
        records = await cls.bot.db.fetch(
            f"""
            SELECT *
            FROM tags
            WHERE (($1 = ANY(guild_ids)) or 0 = ANY(guild_ids)) AND tag_key % $2
            ORDER BY similarity(tag_key, $2) > {cls.bot.conf.tags.prediction_accuracy} DESC
            LIMIT 10;
            """,
            guild_id, 
            tag_name

        )
        if creator_id:
            return [r for r in records if creator_id in r["author_ids"]]
        return records

        

class Tag():
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @cached(TTLCache, 1024, 120)
    async def is_taken(self) -> bool:
        return True

class TagIsTakenError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)