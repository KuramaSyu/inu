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
import traceback

import asyncpg
from asyncache import cached
from cachetools import TTLCache, LRUCache
import hikari
from hikari import ButtonStyle, Embed
from hikari import Snowflake, User, Member
from hikari.impl import MessageActionRowBuilder
from numpy import column_stack
from asyncache import cached
from cachetools import TTLCache
from tabulate import tabulate

from ..shortcuts import guild_name_or_id, get_guild_or_channel_id, user_name_or_id
from ..language import Human, Multiple
from core.db import Database, Table
from core import Inu, BotResponseError, getLogger

log = getLogger(__name__)


TAG_REGEX = r"""tag:\/{2}(?P<tag_name>(?:[\/\-_,<>*()[{}"'+#^&\s\w\.]*))[.](?P<scope>local|global|this[-]guild|[0-9]+)"""
TAG_NOT_ALLOWED_REGEX = r"[^A-Za-z0-9\/\-,<>*()[\]{}\\\s\"\'\(\)+#^&]+"


class TagType(Enum):
    NORMAL = 0
    MEDIA = 1
    LIST = 2
    VOCABULARY = 3

    @classmethod
    def from_value(cls, value: int) -> "TagType":
        return next((member for name, member in cls.__members__.items() if member.value == value), None)
    
    @classmethod
    def get_name(cls, value: int) -> "str":
        return {
            0: "Normal",
            1: "Media URL",
            2: "List"
        }.get(value, "Unknown")



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
        self.tag_type: TagType = TagType.NORMAL
        self.info_visible: bool = True
        self.uses: int = 0
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
        match = re.match(TAG_REGEX, f"tag://{value}.local")
        if not match:
            # get all invalid characters 
            unallowed_characters = re.findall(TAG_NOT_ALLOWED_REGEX, value)
            raise RuntimeError(f"Some characters are not allowed in `{value}`: `{unallowed_characters}`")
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
                    f"no tag found with name `{tag_info['tag_name']}` {f'in this guild ({current_guild})' if tag_info['scope'] != '0' else 'globally'}.\n"
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
        self.uses += 1
        asyncio.create_task(self._wait_used_now())
    
    async def _wait_used_now(self):
        """updates the last_use column and waits until finished"""
        await TagManager._update_tag_last_use(self.id, self.uses)

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
                tag_type=self.tag_type.value,
                info_visible=self.info_visible,
            )
        else:
            tag_id = await TagManager.set(
                key=self.name,
                value=self.value,
                author_ids=list(self.owners),
                guild_ids=list(self.guild_ids),
                aliases=list(self.aliases),
                tag_type=self.tag_type.value,
                info_visible=self.info_visible,
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
        new_tag.tag_type = TagType.from_value(record["type"])
        new_tag.uses = record["uses"]
        new_tag.info_visible = record["info_visible"]
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

    def is_authorized_to_see(self, guild_or_channel_id: int) -> bool:
        return guild_or_channel_id in self.guild_ids

    def is_authorized_to_write(self, user_id: int) -> bool:
        return user_id in self.owners

    @classmethod
    async def from_id(cls, tag_id: int, user_id: int, guild_or_channel_id: int = 0, only_accessable: bool = True) -> Optional["Tag"]:
        """
        returns a Tag created from the id

        Args:
        -----
        tag_id : int
            the id of the tag
        user_id : int
            the id of a user which should be contained in the tag
        guild_or_channel_id : int = 0
            the guild or channel id which should be contained in that guild
        only_accessable : bool = True
            wether the results should be filtered with the given guilds or users
        """
        if only_accessable:
            d = await TagManager.get(tag_id=tag_id, author_id=user_id, guild_id=guild_or_channel_id, only_accessable=only_accessable)
        else:
            d = [await TagManager.fetch_by_id(tag_id)]
        if not d:
            return None
        return await cls.from_record(d[0])

    def get_embed(self) -> hikari.Embed:
        embed = Embed()
        embed.title = self.tag.name
        embed.description = self.tag.value
        embed.add_field(name="Status", value=str(self))
        return embed

    async def fetch(self) -> None:
        """
        Fetches the tag from the database. Updates value, name etc.
        """
        tag = await Tag.from_id(self.id, user_id=0, only_accessable=False)
        if tag is None:
            raise RuntimeError(f"Tag with id {self.id} not found")
        self = tag

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

    def __str__(self):
        return self.to_string()
    
    def to_string(self, current_page: int | None = None, fields: str = "all") -> str:
            """
            Convert the Tag object to a string representation.

            Args:
                current_page : int | None, optional
                    The current page number. Defaults to None.
                fields : Literal["all", "static", "dynamic", "to_do"], optional
                    The fields to include in the string representation. Defaults to "all".
                    Other Options

            Returns:
                str: The string representation of the Tag object.
            """
            msg = ""
            characters_prefix = "["
            characters_suffix = "]"
            if len(self.value) == 1:
                characters_prefix = ""
                characters_suffix = ""
            data = [
                ["Guilds", f"{', '.join(guild_name_or_id(id) for id in self.guild_ids)}"],
                ["Owners", f"{', '.join(user_name_or_id(o) for o in self.owners)}"],
            ]
            if current_page is None:
                data.append(["Message", f"{characters_prefix}{' | '.join([str(len(p)) for p in self.value])}{characters_suffix}/2048 Letters"])
            if self.aliases:
                data.append(["Aliases", f"{', '.join(f'`{alias}`' for alias in self.aliases)}"])
            data_size_known = {
                "Tag type": [f"{self.tag_type.get_name(self.tag_type.value)}"],
                "Uses": [f"{self.uses}"],
            }
            if current_page is not None:
                data_size_known["Message"] = [f"{len(self.value[current_page])}/2048 Letters"]
            if fields in ["all", "dynamic"]:
                msg += f"{tabulate(data, tablefmt='rounded_grid', maxcolwidths=[10, 50])}"
            if fields in ["all", "static"]:
                msg += f"{tabulate(data_size_known, tablefmt='rounded_grid', headers=['Type', 'Uses', 'Page size'])}"

            if to_do := self.to_do and fields in ["all", "to_do"]:
                msg += (
                    f"{to_do}"
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
    def components(self) -> List[MessageActionRowBuilder] | None:
        """
        Returns a list of components of the tag.
        """
        if not self.tag_link_infos:
            return None
        if len(self.tag_link_infos) < 6:
            action_row = MessageActionRowBuilder()
            for link in self.tag_link_infos:
                (
                    action_row
                    .add_interactive_button(
                        ButtonStyle.SECONDARY, 
                        f"tag://{link['tag_name']}.{link['scope']}",
                        label=link["tag_name"]
                    )
                )
        else:
            action_row = MessageActionRowBuilder().add_text_menu(f"tag-link-menu")
            for link in self.tag_link_infos[:24]:
                action_row.add_option(
                    f"{link['tag_name']}", 
                    f"tag://{link['tag_name']}.{link['scope']}"
                )
            action_row = action_row.parent
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
            for link in self.tag_link_infos:
                c_ids.append(f"tag://{link['tag_name']}.{link['scope']}")
        else:
            c_ids.append(f"{self.name}-link-menu")
        return c_ids


class TagScope(Enum):
    YOUR = 1
    GUILD = 2
    GLOBAL = 3
    SCOPE = 4



class TagManager():
    db: Database
    bot: Inu
    table: Table

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
        cls.table = Table("tags")


    @classmethod
    async def set(
        cls, 
        key: str,
        value: str,
        author_ids: List[int],
        guild_ids: List[int],
        aliases: List[str],
        check_if_taken: bool = True,
        tag_type: int = 0,
        info_visible: bool = True,
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
            INSERT INTO tags(tag_key, tag_value, author_ids, guild_ids, aliases, last_use, type, info_visible)
            VALUES($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING tag_id
            """,
            key,
            value,
            author_ids,
            guild_ids,
            aliases,
            datetime.now(),
            tag_type,
            info_visible,
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
        tag_type: Optional[int] = None,
        info_visible: Optional[bool] = None,
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
        if tag_type is not None:
            new_record["type"] = tag_type
        if info_visible is not None:
            new_record["info_visible"] = info_visible
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
        key: str | None = None,
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
        key: Optional[str]
            the key to search
        guild_id: int = 0
            the guild_id the tag should have
        authod_id: int = 0
            an author id which should be contained in the tag
        only_accessable: (bool) 
            wehter or not the function should return only 
            the gobal and/or local one instead of every tag with matching `key`
        tag_id : int
            the id of the tag to fetch. Default -1 -> not existent

        Note:
        -----
            - either `<key>` or `<tag_id>` is needed
            - 0 for guild_id is equivilant with `global` tag
        """
        table = Table("tags")
        sql = f"""
            SELECT * FROM tags
            WHERE
                ( 
                    tag_key = $1 
                    OR $1 = ANY(aliases) 
                    OR $4::INT = tag_id
                ) 
                AND 
                ( 
                    $2::BIGINT = ANY(guild_ids) 
                    OR 0 = ANY(guild_ids)
                    OR $3::BIGINT = ANY(author_ids)
                ) 
            """
        if key is None and tag_id == -1:
            raise RuntimeError("neither `<tag_id>` nor `<key>` where passed into the function")
        records: Optional[List[Mapping[str, Any]]] = await table.fetch(sql, key, guild_id, author_id, tag_id)
        return records or []

    @classmethod
    async def sync_record(
        cls,
        record: Mapping[str, Any],
    ):
        """
        Updates a record in the db

        Args:
        -----
        `record: Mapping[str, Any] `
            the record which should be updated
        `old_record: Mapping[str, Any] `
            the old record, how it is stored in the db
        
        """
        sql = """
            UPDATE tags
            SET (tag_value, tag_key, author_ids, guild_ids, aliases, last_use, type, info_visible) = ($1, $2, $3, $4, $5, $6, $8, $9)
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
            record["type"],
            record["info_visible"],
        )
    @classmethod
    async def fetch_by_id(cls, tag_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetches a tag by ID
        """
        sql = """
        SELECT * FROM tags
        WHERE tag_id = $1
        RETURNING *
        """
        record = await cls.db.row(sql, tag_id)
        if not record:
            return None
        return record
    
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
    async def _update_tag_last_use(cls, tag_id: int, tag_uses: int):
        table = Table("tags")
        
        await table.update({"last_use": datetime.now(), "uses": tag_uses}, {"tag_id": tag_id})
    
    @classmethod
    async def get_tags(
        cls, 
        type: TagScope, 
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
        if type == TagScope.GLOBAL:
            sql = f"{sql} WHERE 0 = ANY(guild_ids) {after_sql}"
            return await cls.db.fetch(sql)
        elif type == TagScope.GUILD:
            if guild_id is None:
                raise RuntimeError("Can't fetch tags of a guild without an id (id is None)")
            sql = f"{sql} WHERE $1 = ANY(guild_ids) {after_sql}"
            return await cls.db.fetch(sql, guild_id)
        elif type == TagScope.YOUR:
            if author_id is None:
                raise RuntimeError("Can't fetch tags of a creator without an id (id is None)")
            sql = f"{sql} WHERE $1 = ANY(author_ids) {after_sql}"
            return await cls.db.fetch(sql, author_id)
        elif type == TagScope.SCOPE:
            if guild_id is None:
                raise RuntimeError("Can't fetch tags of a guild without an id (id is None)")
            sql = f"{sql} WHERE $1 = ANY(guild_ids) OR 0 = ANY(guild_ids) {after_sql}"
            return await cls.db.fetch(sql, guild_id)
        raise RuntimeError(f"TagType unmatched - {type}")
    

    @classmethod
    @cached(TTLCache(1024, 30))
    async def cached_find_similar(
        cls,
        tag_name: str, 
        guild_id: Optional[int], 
        creator_id: Optional[int] = None,
        tag_type: Optional[TagType] = None,
    ) -> List[Dict[str, Any]]:
        return await cls.find_similar(tag_name, guild_id, creator_id, tag_type)


    @classmethod
    async def find_similar(
        cls,
        tag_name: str, 
        guild_id: Optional[int], 
        creator_id: Optional[int] = None,
        tag_type: Optional[TagType] = None,
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
        cols = ["guild_ids", "tag_key"]
        vals = [guild_id, tag_name]
        extra_where_statement = []
        dollar = (f'${num}' for num in range(3,99))
        if creator_id:
            vals.append(creator_id)
            extra_where_statement.append(f"{next(dollar)} = ANY(creator_ids) ")

        if tag_type is not None:
            vals.append(tag_type.value)
            extra_where_statement.append(f"type = {next(dollar)}")

        extra_where_statement = " AND ".join(extra_where_statement)
        if extra_where_statement:
            extra_where_statement = f"AND ({extra_where_statement})"
        
        records = await cls.bot.db.fetch(
            f"""
            SELECT *
            FROM tags
            WHERE 
                (
                    ($1 = ANY(guild_ids)
                    OR 0 = ANY(guild_ids))
                    {extra_where_statement}
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
            *vals
        )
        # if creator_id:
        #     return [r for r in records if creator_id in r["author_ids"]]
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

    @classmethod
    async def tag_name_auto_complete(
        cls,
        option: hikari.AutocompleteInteractionOption, 
        interaction: hikari.AutocompleteInteraction
    ) -> List[str]:
        """autocomplete for tag keys"""
        guild_or_channel = get_guild_or_channel_id(interaction)
        try:
            if option.value and len(str(option.value)) > 2:
                tags = await cls.find_similar(option.value, guild_id=guild_or_channel)
                return [tag['tag_key'] for tag in tags][:24]
            elif option.value and len(str(option.value)) in [1, 2]:
                tags = await cls.startswith(option.value, guild_id=guild_or_channel)
                return [
                    name for name in 
                    [
                        *[name for tag in tags for name in tag["aliases"]], 
                        *[tag['tag_key'] for tag in tags]
                    ] 
                    if name.startswith(option.value) ][:24]
            else:
                tags = await cls.get_tags(
                    type=TagScope.SCOPE,
                    guild_id=guild_or_channel,
                    limit=25
                )
                return [tag["tag_key"] for tag in tags][:24]

        except:
            log.error(traceback.format_exc())
            return []
        
    @classmethod
    async def fetch_guild_tag_amount(cls, guild_id: int) -> int:
        """
        Fetches the amount of tags in a guild

        Args:
        -----
        guild_id: int
            the guild id to fetch the amount of tags for
        """
        table = Table("tags")
        return (await table.fetch(
            f"""
            SELECT COUNT(*) as tag_amount FROM tags
            WHERE $1 = any(guild_ids) 
            """,
            guild_id
        ))[0]["tag_amount"]


class TagIsTakenError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)

