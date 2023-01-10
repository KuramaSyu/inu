from threading import local
from typing import (
    Dict,
    Optional,
    List,
    Tuple,
    Union,
    Mapping,
    Any,
    Set
)
import asyncio
import typing
from copy import deepcopy
from enum import Enum
import re
from datetime import datetime

import asyncpg
from asyncache import cached
from cachetools import TTLCache, LRUCache
import hikari
from hikari import ButtonStyle, Embed
from hikari import Snowflake, User, Member
from hikari.impl import ActionRowBuilder
from numpy import column_stack
from asyncache import cached
from cachetools import TTLCache

from ..language import Human, Multiple
from core.db import Database, Table
from core import Inu, BotResponseError, getLogger

log = getLogger(__name__)


TAG_REGEX = r"tag:\/{2}(?P<tag_name>(?:\w+[\/\-_,<>*()[{}]*\\*\[*\)*\"*\'*\s*)+)[.](?P<scope>local|global|this[-]guild|[0-9]+)"

class Tag():
    def __init__(self, owner: Optional[hikari.User] = None, channel_id: Optional[hikari.Snowflakeish] = None):
        """
        A class which represents a tag
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
        self.owners: Set[hikari.Snowflake] = set([owner.id]) if owner else set()
        self._name: Optional[str] = None
        self.value: Optional[List[str]] = None
        self.is_local_available: bool
        self.is_global_available: bool
        self._is_local: bool = True
        self.is_stored: bool = False
        self._id: Optional[int] = None
        self.aliases: Set[str] = set()
        self.guild_ids: Set[int] = set()
        if isinstance(owner, hikari.Member):
            self.guild_ids.add(owner.guild_id)
            self._is_local = True
        else:
            if channel_id:
                self.guild_ids.add(channel_id)
                self._is_local = True
            else:
                self.guild_ids.add(0)
                self._is_local = False

    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, value):
        
        if len(str(value)) > 256:
            raise RuntimeError("Can't store a tag with a name bigger than 256 chars")
        if not re.match(TAG_REGEX, f"tag://{value}.local"):
            raise RuntimeError("Some characters are not allowed in the tag name")
        self._name = value

    @property
    def link(self):
        return f"tag://{self.name}.{'this-guild' if self.is_local else 'global'}"

    @property
    def tag_links(self) -> List[str]:
        if not self.value:
            raise RuntimeError("Can't get tag links without a value")
        return [f"tag://{info['tag_name']}.{info['scope']}"  for info in self._get_links("\n".join(self.value))]

    @property
    def tag_link_infos(self) -> List[str]:
        if not self.value:
            raise RuntimeError("Can't get tag links without a value")
        return self._get_links("\n".join(self.value))

    @classmethod
    def _get_links(cls, value: str) -> List[Dict[str, str]]:
        """
        Returns a list of links in the value
        """
        return [{"tag_name":t[0], "scope":t[1]} for t in re.findall(TAG_REGEX, value)]

    @property
    def is_local(self) -> bool:
        return not 0 in self.guild_ids


    @property
    def id(self) -> int:
        if not self._id:
            raise RuntimeError("Can't store an ID without a number")
        return self._id
    
    @id.setter
    def id(self, value):
        self._id = value

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
        
    @classmethod
    async def fetch_tag_from_link(cls, link: str, current_guild: int) -> Optional["Tag"]:
        """
        Fetches a tag from a link.
        
        Returns:
        -------
        Tag | None:
            returns Tag if link is valid and None if it isn't a tag link
        
        Raises:
        -------
        BotResoponseError :
            when tag link is correct, but tag was not found
        """
        try:
            tag_info = cls._get_links(link)[0]
        except IndexError:
            return None
        tag_info["scope"] = (
            tag_info["scope"]
            .replace("this-guild", str(current_guild))
            .replace("local", str(current_guild))
            .replace("global", "0")
        )
        records = await TagManager.get(tag_info["tag_name"], int(tag_info["scope"]))
        if not records:
            raise BotResponseError(
                str(
                    f"Tag doesn't existent here - "
                    f"no tag found with name `{tag_info['tag_name']}` {'in this guild' if tag_info['scope'] != '0' else 'globally'}.\n"
                    f"Maybe the tag is available in another guild, but not shared with this one?\n"
                    f"You could ask the person who should own this tag to share it with your guild.\n"
                    f"The command is `/tag add-guild`\n"
                    f"Otherwise you can also create the tag with `/tag add`"
                ),
                ephemeral=True,
            )
        return await cls.from_record(records[0], db_checks=False)

    async def used_now(self):
        """Adds a asyncio task to update the tag last_use column"""
        asyncio.create_task(self._wait_used_now())
    
    async def _wait_used_now(self):
        """updates the last_use column and waits until finished"""
        await TagManager._update_tag_last_use(self.id)

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
                value=[value for value in self.value if value],  # remove empty pages
                author_ids=list(self.owners),
                tag_id=self.id,
                guild_ids=list(self.guild_ids),
                aliases=list(self.aliases),
            )
        else:
            tag_id = await TagManager.set(
                key=self.name,
                value=self.value,
                author_ids=list(self.owners),
                guild_ids=list(self.guild_ids),
                aliases=list(self.aliases),
            )
            self.id = tag_id
        self.is_stored = True

    @classmethod
    async def from_record(cls, record: Mapping[str, Any], author: hikari.User = None, db_checks: bool = True) -> "Tag":
        """
        loads an existing tag in form of a dict like object into self.tag (`Tag`)
        Args:
        -----
        record: Mapping[str, Any]
            the tag which should be loaded
        author: Member | User 
            the user which stored the tag
        db_checks: bool
            wether or not checking db for tag availability (update local/global taken)
        """
        if db_checks:
            local_taken, global_taken = await TagManager.is_taken(key=record["tag_key"], guild_ids=record["guild_ids"])
        else:
            local_taken, global_taken = True, True
        new_tag = cls()
        new_tag.name = record["tag_key"]
        new_tag.value = record["tag_value"]
        new_tag.is_stored = True
        new_tag.id = record["tag_id"]
        new_tag.guild_ids = set(record["guild_ids"])
        new_tag.aliases = set(record["aliases"])
        new_tag.owners = set(record["author_ids"])
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

    async def is_authorized_to_see(self, user: hikari.Member | hikari.User) -> bool:
        return

    @classmethod
    async def from_id(cls, tag_id: int, user: hikari.Member | hikari.User) -> Optional[Mapping[str, Any]]:
        """
        
        """
        d = await TagManager.get_from_id(tag_id)
        if not d:
            return None
        return await cls.from_record(d)

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
        tag = Tag()
        tag.owners = self.owners
        tag.name = None
        tag.value = None
        tag.is_stored = False
        if isinstance(author, hikari.Member):
            tag._is_local = True
        else:
            tag._is_local = False
        tag.is_global_available = False
        tag.is_local_available = False
        Tag._initialize_embed(tag)
        self = tag

    def _initialize_embed(self):
        self.embed = Embed()
        self.embed.title = self.tag.name or "Name - Not set"
        self.embed.description = self.tag.value or "Value - Not set"
        self.embed.add_field(name="Status", value=str(self.tag))
        self._pages = [self.embed]

    def __str__(self) -> str:
        msg = (
            f"your tag is: {'local' if self.is_local else 'global'}\n"
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

        Note:
        -----
            - is a coroutine
            - can be expensive
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

    @property
    def components(self) -> List[ActionRowBuilder] | None:
        """
        Returns a list of components of the tag.
        """
        if not self.tag_link_infos:
            return None
        if len(self.tag_link_infos) < 6:
            action_row = ActionRowBuilder()
            for link in self.tag_link_infos:
                (
                    action_row
                    .add_button(ButtonStyle.SECONDARY, f"tag://{link['tag_name']}.{link['scope']}")
                    .set_label(link["tag_name"])
                    .add_to_container()
                )
        else:
            action_row = ActionRowBuilder().add_select_menu(f"tag-link-menu")
            for link in self.tag_link_infos[:24]:
                action_row = (
                    action_row
                    .add_option(f"{link['tag_name']}", f"tag://{link['tag_name']}.{link['scope']}").add_to_menu()
                )
            action_row = action_row.add_to_container()
        return [action_row]

    @property
    def component_custom_ids(self) -> List[str] | None:
        """
        Returns a list of custom ids of the tag.
        """
        if not self.tag_link_infos:
            return None

        c_ids = []
        if len(self.tag_link_infos) < 6:
            action_row = ActionRowBuilder()
            for link in self.tag_link_infos:
                c_ids.append(f"tag://{link['tag_name']}.{link['scope']}")
        else:
            c_ids.append(f"{self.name}-link-menu")
        return c_ids


class TagType(Enum):
    YOUR = 1
    GUILD = 2
    GLOBAL = 3
    SCOPE = 4



class TagManager():
    db: Database
    bot: Inu

    def __init__(self, key: Optional[str] = None):
        self.key = key

    @classmethod
    def _strip_key(cls, key: str):
        return key.strip(" ")
    
    @classmethod
    def _key_raise_if_not_allowed(cls, key: str) -> None:
        """
        Raises RuntimeError if not allowed
        """
        if len(key) > 255:
            raise RuntimeError(f"`{Human.short_text(key, 255)}` is longer than 255 characters")
        elif (char := Multiple.startswith_(key, [" "])):
            raise RuntimeError(f"`{key}` mustn't start with `{char}`")
        elif (char := Multiple.endswith_(key, [" "])):
            raise RuntimeError(f"`{key}` mustn't end with `{char}`")
        # elif " " in key:
        #     raise RuntimeError(f"`{key}` mustn't contain a space")

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
        key = cls._strip_key(key)
        #guild_id = author.guild_id if isinstance(author, hikari.Member) else None #type: ignore
        if 0 in guild_ids:
            # when a local tag changes scope to global, the guilds wont be deleted
            # hence, the check would fail, since these are still in
            guild_ids = [0]
        for guild_id in guild_ids:
            await cls._do_check_if_taken(key, guild_id, check_if_taken)
        record = await cls.db.row(
            """
            INSERT INTO tags(tag_key, tag_value, author_ids, guild_ids, aliases, last_use)
            VALUES($1, $2, $3, $4, $5, $6)
            RETURNING tag_id
            """,
            key,
            value,
            author_ids,
            guild_ids,
            aliases,
            datetime.now(),
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
        key = cls._strip_key(key)
        # guild_id = author.guild_id if isinstance(author, hikari.Member) else None
        guild_ids = guild_ids or [0]
        for guild_id in guild_ids:
            await cls._do_check_if_taken(key, guild_id, check_if_taken)
        record = await cls.db.row(sql, tag_id)
        new_record = {k: v for k, v in record.items()}
        new_record["last_use"] = datetime.now()
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
        only_accessable: bool = True,
        tag_id: Optional[int] = -1,
    ) -> List[Mapping[str, Any]]:
        """
        Returns the tag of the key, or multiple, if overridden in guild.
        This function is a corotine.

        Args:
        -----
        key: (str) 
            the key to search
        guild_id: (int) [default None] 
            the guild_id the tag should have
        only_accessable: (bool) 
            wehter or not the function should return only 
            the gobal and/or local one instead of every tag with matching `key`
        tag_id : int
            the id of the tag to fetch. Default -1 -> not existent

        Note:
        -----
            - 0 is equivilant with `global` tag
        """
        sql = f"""
            SELECT * FROM tags
            WHERE (tag_key = $1 OR $1 = ANY(aliases) OR $4 = tag_id) 
            AND (
                    ($2::BIGINT = ANY(guild_ids) 
                    OR 0 = ANY(guild_ids)) 
                    OR $3 = ANY(author_ids)
                )
            """
        records: Optional[List[Mapping[str, Any]]] = await cls.db.fetch(sql, key, guild_id, author_id, tag_id)
        return records or []
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
    async def get_from_id(cls, tag_id: int, user_id: int = 0, guild_id: int = 0) -> Optional[Mapping[str, Any]]:
        """
        Args:
        -----
        tag_id : int
            id of the tag
        user_id : int
            id of the user to check if user has permission
        guild_id : int
            id of guild to check if tag is permitted in guild
        Returns:
        --------
        Mapping[str, Any] | None
            the tag from the id. None, if id was not found
        """
        table = Table("tags")
        return await table.select_row(columns=["tag_id"], matching_values=[tag_id])

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
            SET (tag_value, tag_key, author_ids, guild_ids, aliases, last_use) = ($1, $2, $3, $4, $5, $6)
            WHERE tag_id = $7
            """
        await cls.db.execute(
            sql,
            record["tag_value"],
            record["tag_key"],
            list(record["author_ids"]),
            list(record["guild_ids"]),
            list(record["aliases"]),
            record["last_use"],
            record["tag_id"],
        )

    @classmethod
    async def is_global_taken(cls, key: str, tags: Optional[List[str]] = None):
        """
        checks if the key is in tag_key column

        Args:
        -----
        key: str
            the key to search
        tags: List[str]
            an already fetched column (list) of all tags


        Raises:
        -------
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
        -----
        key: str
            the key to match for#
        guild_id: int
            the guild if to check for.
            NOTE: if its 0 it will only check global, otherwise only local
        check: bool
            wether the check should be executed or not
            (wether to raise TagIsTakenError)

        Raises:
        -------
        utils.tag_manager.TagIsTakenError: 
            if Tag is taken (wether gobal or local see guild_id)
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
    async def _update_tag_last_use(cls, tag_id: int):
        table = Table("tags")
        await table.update({"last_use": datetime.now()}, {"tag_id": tag_id})
    
    @classmethod
    async def get_tags(
        cls, 
        type: TagType, 
        guild_id: Optional[int] = None, 
        author_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get all tags of a specific type (you, guild, in scope..)

        Args:
        -----
        type: TagType
            the type of tags to get
        guild_id: int
            the guild id to get tags for
        author_id: int
            the author id to get tags for
        
        Note:
        -----
            - depending on type, guild_id and/or author_id is used
        """
        sql = """
            SELECT * FROM tags
            """
        after_sql = """
        ORDER BY last_use DESC
        """
        if limit:
            after_sql += f" LIMIT {limit}"
        if type == TagType.GLOBAL:
            sql = f"{sql} WHERE 0 = ANY(guild_ids) {after_sql}"
            return await cls.db.fetch(sql)
        elif type == TagType.GUILD:
            if guild_id is None:
                raise RuntimeError("Can't fetch tags of a guild without an id (id is None)")
            sql = f"{sql} WHERE $1 = ANY(guild_ids) {after_sql}"
            return await cls.db.fetch(sql, guild_id)
        elif type == TagType.YOUR:
            if author_id is None:
                raise RuntimeError("Can't fetch tags of a creator without an id (id is None)")
            sql = f"{sql} WHERE $1 = ANY(author_ids) {after_sql}"
            return await cls.db.fetch(sql, author_id)
        elif type == TagType.SCOPE:
            if guild_id is None:
                raise RuntimeError("Can't fetch tags of a guild without an id (id is None)")
            sql = f"{sql} WHERE $1 = ANY(guild_ids) OR 0 = ANY(guild_ids) {after_sql}"
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
        tag_name : `str` 
            the name of the tag, to search
        guild_id : `int` 
            the guild_id, which the returning tags should have
        creator_id : `int` | None
            the creator_id, which the returning tags should have

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
            WHERE 
                (
                    ($1 = ANY(guild_ids)) 
                    OR 0 = ANY(guild_ids)
                ) 
                    AND
                (
                    similarity(tag_key, $2) > {cls.bot.conf.tags.prediction_accuracy} 
                    OR EXISTS 
                    (
                        SELECT alias 
                        FROM unnest(aliases) 
                        AS alias 
                        WHERE similarity(alias, $2) > {cls.bot.conf.tags.prediction_accuracy} 
                    )
                )
            ORDER BY similarity(tag_key, $2) DESC
            LIMIT 20;
            """,
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
        creator_id: Optional[int] = None,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        ### searches tags which start with <`start_with`> in every reachable scope

        Args:
        -----
        tag_name : `str`
            the name of the tag, to search
        guild_id : `int`
            the guild_id, which the returning tags should have
        creator_id : `int` | None)
            the creator_id, which the returning tags should have

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
                        OR EXISTS 
                        (
                            SELECT alias 
                            FROM unnest(aliases) 
                            AS alias 
                            WHERE starts_with(alias, $2)
                        )
                    )
                )
            ORDER BY last_use DESC
            LIMIT {limit}
            """,
            guild_id, 
            starts_with,
        )
        if creator_id:
            return [r for r in records if creator_id in r["author_ids"]]
        return records


class TagIsTakenError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)

