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
from hikari import Embed
from hikari import Snowflake, User, Member
from numpy import column_stack
from asyncache import cached
from cachetools import TTLCache

from ..language import Human, Multiple
from core.db import Database, Table
from core import Inu


class TagProxy():
    def __init__(self, owner: hikari.User, channel_id: Optional[hikari.Snowflakeish] = None):
        """
        Members:
        --------
            - is_local: (bool) if tag is local or global. default=True if invoked from guild else default=False
            - owner: (User | Member) the owner of the Tag
            - name: (str) the key of the tag
            - is_local_available: (bool) whether or not the tag can be stored local
            - is_global_available: (bool) whter or not the tag can be stored global
            - is_stored: (bool) wether or not the tag is already in the db stored
        NOTE:
        -----
            - the owner should be an instace of `Member`, to be able, to store an tag locally
            otherwise the tag have to be stored globally
        """
        self.owners: List[hikari.Snowflake] = [owner.id]
        self._name: Optional[str] = None
        self.value: Optional[str] = None
        self.is_local_available: bool
        self.is_global_available: bool
        self._is_local: bool = True
        self.is_stored: bool
        self._id: Optional[int] = None
        self.aliases: List[str] = []
        self.guild_ids: List[int] = []
        if isinstance(owner, hikari.Member):
            self.guild_ids.append(owner.guild_id)
            self._is_local = True
        else:
            if channel_id:
                self.guild_ids.append(channel_id)
                self._is_local = True
            else:
                self.guild_ids.append(0)
                self._is_local = False

    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, key):
        
        if len(key) > 255:
            raise RuntimeError(f"`{Human.short_text(key, 255)}` is longer than 255 characters")
        elif (char := Multiple.startswith_(" ")):
            raise RuntimeError(f"`{key}` mustn't start with `{char}`")
        elif (char := Multiple.endswith_(" ")):
            raise RuntimeError(f"`{key}` mustn't end with `{char}`")
        elif " " in key:
            raise RuntimeError(f"`{key}` mustn't contain a space")
        self._name = key

    @property
    def is_local(self) -> bool:
        return self._is_local


    @property
    def id(self) -> int:
        if not self._id:
            raise RuntimeError("Can't store an ID without a number")
        return self._id

    @property
    def to_do(self) -> Optional[str]:
        """returns a string with things which have to be done before storing the tag"""
        to_do_msg = ""
        if self.name is None:
            to_do_msg += "- Enter a name\n"
        if self.value is None:
            to_do_msg += "- Enter a value\n"
        if (
            not self.is_stored
            and self._is_local
            and not self.is_local_available
        ):
            to_do_msg += "- Your tag isn't local available -> change the name\n"
        if (
            not self.is_stored
            and not self._is_local
            and not self.is_global_available
        ):
            to_do_msg += "- Your tag isn't global available -> change the name\n"
        return to_do_msg or None
        

    async def save(self):
        """
        Saves the current tag.

        Raises:
        -------
            - TagIsTakenError
        """
        if not self.name or not self.value:
            raise RuntimeError("I can't store a tag without a name and value")
        if self.is_stored:
            await TagManager.edit(
                key=self.name,
                value=self.value,
                author_ids=self.owners,
                tag_id=self.id,
                guild_ids=self.guild_ids,
                aliases=self.aliases,
            )
        else:
            tag_id = await TagManager.set(
                key=self.name,
                value=self.value,
                author_ids=self.owners,
                guild_ids=self.guild_ids,
                aliases=self.aliases,
            )
            self.id = tag_id
        self.is_stored = True

    @classmethod
    async def from_record(cls, record: Mapping[str, Any], author: hikari.User) -> "Tag":
        # """
        # loads an existing tag in form of a dict like object into self.tag (`Tag`)
        # Args:
        # -----
        #     - tag: (Mapping[str, Any]) the tag which should be loaded
        #     - author: (Member, User) the user which stored the tag
        # """
        # guild_id = self.owner.guild_id if isinstance(self.owner, hikari.Member) else 0
        # local_taken, global_taken = await TagManager.is_taken(key=self.tag.name, guild_id = guild_id or 0)
        # self.name = tag["tag_key"]
        # self.value = tag["key_value"]
        # self.is_stored = True
        # self.id = tag["tag_id"]
        # self.is_global_available = not global_taken
        # self.is_local_available = not local_taken

        """
        loads an existing tag in form of a dict like object into self.tag (`Tag`)
        Args:
        -----
            - record: (Mapping[str, Any]) the tag which should be loaded
            - author: (Member, User) the user which stored the tag
        """
        local_taken, global_taken = await TagManager.is_taken(key=record["tag_key"], guild_ids=record["guild_ids"])
        new_tag: cls = cls(author)
        new_tag.name = record["tag_key"]
        new_tag.value = record["tag_value"]
        new_tag.is_stored = True
        new_tag.id = record["tag_id"]
        new_tag.guild_ids = record["guild_ids"]
        new_tag.aliases = record["aliases"]
        new_tag.owners = record["author_ids"]
        if (
            isinstance(author, hikari.Member)
            and not 0 in record["guild_ids"]
            and author.guild_id in record["guild_ids"]
        ):
            new_tag._is_local = True
        else:
            new_tag._is_local = False
        new_tag.is_global_available = not global_taken
        new_tag.is_local_available = not local_taken
        return new_tag

    def get_embed(self) -> hikari.Embed:
        embed = Embed()
        embed.title = self.tag.name
        embed.description = self.tag.value
        embed.add_field(name="Status", value=str(self))
        return embed

    async def prepare_new_tag(self, author: Union[hikari.Member, hikari.User]):
        """
        creates a new tag in form of `Tag`
        Args:
        -----
            - author: (Member, User) the user which stored the tag
        """
        tag = Tag(self.owner)
        tag.name = None
        tag.value = None
        tag.is_stored = False
        if isinstance(author, hikari.Member):
            tag._is_local = True
        else:
            tag._is_local = False
        tag.is_global_available = False
        tag.is_local_available = False
        self.tag = tag

        self.embed = Embed()
        self.embed.title = self.tag.name or "Name - Not set"
        self.embed.description = self.tag.value or "Value - Not set"
        self.embed.add_field(name="Status", value=str(self.tag))
        self._pages = [self.embed]

    def __str__(self) -> str:
        msg = (
            f"your tag is: {'local' if self._is_local else 'global'}\n"
            f"the owners are: {', '.join(f'<@{o}>' for o in self.owners)}\n"
            f"is the tag stored: {Human.bool_(self.is_stored)}\n"
            f"available for guilds: {', '.join(str(id) for id in self.guild_ids)}\n"
            f"is the tag name local available: {Human.bool_(self.is_local_available)}\n"
            f"is the tag name global available: {Human.bool_(self.is_global_available)}\n"
        )
        if self.aliases:
            msg += f"aliases: {', '.join(self.aliases)}\n"
        if to_do := self.to_do:
            msg += (
                f"\n**TO DO:**\n{to_do}"
            )
        return msg

    async def update(self) -> None:
        """
        Updates self.is_global_available and self.is_local_available
        - is a coroutine
        """
        self.is_global_available = True
        self.is_local_available = True
        local_taken, global_taken = await TagManager.is_taken(self.name, self.guild_ids)
        if local_taken:
            self.is_local_available = False
        if global_taken:
            self.is_global_available = False

    async def delete(self):
        """Deletes this tag from the database if it is already stored"""
        if not self.is_stored:
            return
        await TagManager.remove(self.id)
        self.is_stored = False
        return

class TagType(Enum):
    YOUR = 1
    GUILD = 2
    GLOBAL = 3
    SCOPE = 4



class TagManager():
    db: Database
    
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @classmethod
    def _key_raise_if_not_allowed(key: str) -> None:
        """
        Raises RuntimeError if not allowed
        """
        if len(key) > 255:
            raise RuntimeError(f"`{Human.short_text(key, 255)}` is longer than 255 characters")
        elif (char := Multiple.startswith_(" ")):
            raise RuntimeError(f"`{key}` mustn't start with `{char}`")
        elif (char := Multiple.endswith_(" ")):
            raise RuntimeError(f"`{key}` mustn't end with `{char}`")
        elif " " in key:
            raise RuntimeError(f"`{key}` mustn't contain a space")

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
        if key:
            new_record["tag_key"] = key
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
    async def get_tags(
        cls, 
        type: TagType, 
        guild_id: Optional[int] = None, 
        author_id: Optional[int] = None,
    ) -> Optional[List[Dict[str, Any]]]:
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
        elif type == TagType.SCOPE:
            if guild_id is None:
                raise RuntimeError("Can't fetch tags of a guild without an id (id is None)")
            sql = f"{sql} WHERE $1 = ANY(guild_ids) OR 0 = ANY(guild_ids)"
            return await cls.db.fetch(sql, guild_id)
        raise RuntimeError(f"TagType unmatched - {type}")
    
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
            WHERE (($1 = ANY(guild_ids)) or 0 = ANY(guild_ids)) AND similarity(tag_key, $2) > {cls.bot.conf.tags.prediction_accuracy} 
            ORDER BY similarity(tag_key, $2) DESC
            LIMIT 20;
            """,
            # tag_key % $2
            # > 
            guild_id, 
            tag_name

        )
        if creator_id:
            return [r for r in records if creator_id in r["author_ids"]]
        return records

    @classmethod
    async def startswith(
        cls,
        starts_with: str, 
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
        table = Table("tags")
        records = await table.fetch(
            f"""
            SELECT *
            FROM tags
            WHERE 
                (
                    ($1 = ANY(guild_ids) or 0 = ANY(guild_ids)) 
                    AND 
                    (
                        starts_with(tag_key, $2) 
                        or EXISTS 
                        (
                            SELECT alias 
                            FROM unnest(aliases) 
                            AS alias 
                            WHERE starts_with(alias, $2)
                        )
                    )
                )
            """,
            #(
            # > {cls.bot.conf.tags.prediction_accuracy} 
            #             LIMIT 20;
            guild_id, 
            starts_with,
        )
        if creator_id:
            return [r for r in records if creator_id in r["author_ids"]]
        return records

class TagManagerCached():
    db: Database
    
    def __init__(self, tag_manager: TagManager):
        self.tag_manager = tag_manager

    @classmethod
    def init_db(cls, bot: Inu):
        cls.db = bot.db
        cls.bot = bot

    async def update_cache(self, guild_id: int, tag_key: str):
        pass


    @classmethod
    @cached(TTLCache(3000, float(5*60)))
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

    
    @classmethod
    async def get_tags(
        cls, 
        type: TagType, 
        guild_id: Optional[int], 
        author_id: Optional[int]
    ) -> Optional[List[Dict[str, Any]]]:
        pass
    
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
            WHERE (($1 = ANY(guild_ids)) or 0 = ANY(guild_ids)) AND similarity(tag_key, $2) > {cls.bot.conf.tags.prediction_accuracy} 
            ORDER BY similarity(tag_key, $2) DESC
            LIMIT 20;
            """,
            # tag_key % $2
            # > 
            guild_id, 
            tag_name

        )
        if creator_id:
            return [r for r in records if creator_id in r["author_ids"]]
        return records

    @classmethod
    async def startswith(
        cls,
        starts_with: str, 
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
        table = Table("tags")
        records = await table.fetch(
            f"""
            SELECT *
            FROM tags
            WHERE 
                (
                    ($1 = ANY(guild_ids) or 0 = ANY(guild_ids)) 
                    AND 
                    (
                        starts_with(tag_key, $2) 
                        or EXISTS 
                        (
                            SELECT alias 
                            FROM unnest(aliases) 
                            AS alias 
                            WHERE starts_with(alias, $2)
                        )
                    )
                )
            """,
            #(
            # > {cls.bot.conf.tags.prediction_accuracy} 
            #             LIMIT 20;
            guild_id, 
            starts_with,
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

