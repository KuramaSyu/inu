from enum import Enum
from datetime import datetime, timedelta
from typing import *

import asyncpg
asyncpg.UniqueViolationError

from core import Table, Inu, getLogger

log = getLogger(__name__)


class BoardManager:
    bot: Inu
    # Mapping[guild_id, Dict[emoji, Set[orig message_id]]]
    # Dict has keys emojis (str set) and message_ids (int set)
    # this cache is not aware of, that a message can have multiple reactions
    _cache: Dict[int, Dict[str, Set[int]]] = {}

    @classmethod
    def _cache_add_entry(cls, guild_id: int, emoji: str, message_id: Optional[int]):
        guild_cache = cls._cache.get(guild_id)
        if not guild_cache:
            cls._cache[guild_id] = {
                emoji: set()
            }
            guild_cache = cls._cache[guild_id]

        if guild_cache.get(emoji) is None:
            cls._cache[guild_id][emoji] = set()

        if message_id:
            cls._cache[guild_id][emoji].add(message_id)  # type: ignore

    @classmethod
    def _cache_remove_entry(cls, guild_id: int, emoji: str, message_id: int):
        try:
            cls._cache[guild_id][emoji].remove(message_id)  # type: ignore
        except KeyError:
            pass

    @classmethod
    def _cache_remove_message(cls, guild_id: int, message_id: int):
        try:
            for emoji in cls._cache[guild_id].keys():
                try:
                    cls._cache[guild_id][emoji].remove(message_id)  # type: ignore
                except KeyError:
                    pass
        except KeyError:
            pass

    @classmethod
    def _cache_remove_emoji(cls, guild_id: int, emoji: str):
        try:
            del cls._cache[guild_id][emoji]
        except KeyError:
            pass
    
    @classmethod
    def _cache_remove_guild(cls, guild_id: int):
        try:
            del cls._cache[guild_id]
        except KeyError:
            pass

    @classmethod
    async def init_bot(cls, bot: Inu):
        """
        Set bot and build up cache from db
        """
        cls.bot = bot
        table = Table("board.boards")
        # initialize boards
        records = await table.fetch(f"SELECT guild_id, emoji, enabled FROM {table.name}")
        for record in records:
            if not record["enabled"]:
                continue
            cls._cache_add_entry(
                guild_id=record["guild_id"], 
                emoji=record["emoji"],
                message_id=None,
            )
        # initialize messages
        table = Table("board.entries")
        records = await table.fetch(f"SELECT guild_id, message_id, emoji FROM {table.name}")
        for record in records:
            cls._cache_add_entry(
                guild_id=record["guild_id"], 
                emoji=record["emoji"],
                message_id=record["message_id"],
            )
        log.info(f"initialized BoardManager with {len(records)} entries")


    @classmethod
    def has_emoji(cls, guild_id: int, emoji: str) -> bool:
        return bool(
           cls._cache.get(guild_id, {}).get(emoji) != None
        )

    @classmethod
    def has_message_id(cls, guild_id: int, emoji:str, message_id: int) -> bool:
        return message_id in cls._cache.get(guild_id, {}).get(emoji, [])   

    @classmethod
    async def add_entry(
        cls,
        message_id: int,
        channel_id: int,
        content: Optional[str],
        author_id: int,
        guild_id: int,
        emoji: str,
        attachment_urls: Optional[List[str]],
    ):
        """
        Raises
        ------
        asyncpg.UniqueViolationError:
            When this entry already exists. Should normally not occure

        Note:
        -----
        if entry already exists, then it will be updated
        """
        table = Table("board.entries")
        sql = (
            f"INSERT INTO {table.name}"
        )
        entry = await table.insert(
            which_columns=[
                "message_id", "board_message_id", "channel_id", "content", "author_id",
                "created_at", "guild_id", "emoji", "attachment_urls"
            ],
            values=[
                message_id, None, channel_id, content, author_id, 
                datetime.now(), guild_id, emoji, attachment_urls
            ]
        )
        cls._cache_add_entry(guild_id, emoji, message_id)
        return entry

    @classmethod
    async def edit_entry(
        cls,
        message_id: int,
        emoji: str,
        content: Optional[str] = None,
        board_message_id: Optional[int] = None,
        author_id: Optional[int] = None,

    ):
        """
        Raises
        ------
        asyncpg.UniqueViolationError:
            When this entry already exists. Should normally not occure

        Note:
        -----
        if entry already exists, then it will be updated
        """
        table = Table("board.entries")
        set_: Dict[str, str | int] = {}
        if content:
            set_["content"] = content
        if board_message_id:
            set_["board_message_id"] = board_message_id
        if author_id:
            set_["author_id"] = author_id
        if not set_:
            return
        
        await table.update(
            where={
                "message_id": message_id,
                "emoji": emoji,
            },
            set=set_
        )

    

    @classmethod
    async def remove_entry(
        cls,
        message_id: int,
        emoji: str | None
    ):
        """
        Delete board entry

        Args:
        -----
        message_id: `int`
            the message_id which shouldn't be tracked by the board (original message_id)
        emoji: `str | None`
            the emoji which triggers the board
            NOTE: If it's None, all entries with this message id will be removed (since a message can have different reactions)
        """
        table = Table("board.entries")
        columns = ["message_id"]
        where: List[str | int] = [message_id]
        if emoji:
            columns.append("emoji")
            where.append(emoji)
        records = await table.delete(columns=columns, matching_values=where)
        for record in records:
            cls._cache_remove_entry(record["guild_id"], record["emoji"], record["message_id"])
        return records

    @classmethod
    async def fetch_reactions(
        cls,
        message_id: int,
        emoji: str,
    ) -> List[Dict[str, Any]]:
        table = Table("board.reactions")
        return await table.fetch(
            f"""
            SELECT * FROM {table.name}
            WHERE message_id = $1 and emoji = $2
            """,
            message_id, emoji
        )

    @classmethod
    async def fetch_entry(
        cls,
        message_id: int,
        emoji: str,
    ) -> Optional[Dict[str, Any]]:
        """
        fetches an entry

        Args:
        ----
        message_id : int
            the message id the original message (entry = message + creation date)
        emoji : str
            hence the message can be added to multiple boards, the emoji is needed to destinglish between them
        """
        table = Table("board.entries")
        try:
            return (await table.fetch(
                f"""
                SELECT * FROM {table.name}\n
                WHERE message_id = $1 AND emoji = $2
                """,
                message_id,
                emoji,
            ))[0]
        except IndexError:
            return None

    @classmethod
    async def add_board(
        cls,
        guild_id: int,
        channel_id: int,
        emoji: str,
    ):
        table = Table("board.boards")
        sql = (
            f"INSERT INTO {table.name} (guild_id, channel_id, entry_lifetime, emoji)"
            "VALUES ($1, $2, $3, $4)"
            "ON CONFLICT (guild_id, emoji)"
            "DO"
            "   UPDATE SET channel_id = $2"
        )
        await table.execute(
            sql, 
            guild_id, 
            channel_id,
            timedelta(days=cls.bot.conf.commands.board_entry_lifetime),
            emoji,
        )
        cls._cache_add_entry(guild_id, emoji, None)

    @classmethod
    async def fetch_board(
        cls,
        guild_id: int,
        emoji: str,
        select: str = "*"
    ) -> Optional[Mapping[str, Any]]:
        """
        """
        table = Table("board.boards")
        sql = (
            f"SELECT {select} FROM {table.name}\n"
            "WHERE guild_id = $1 AND emoji = $2"
        )
        try:
            return (await table.fetch(sql, guild_id, emoji))[0]
        except IndexError:
            return None

    @classmethod
    async def remove_board(
        cls,
        guild_id: int,
        emoji: Optional[str] = None,
    ):
        """
        Delete board(s)

        Args:
        -----
        guild_id: `int`
            the guild_id where the board(s) is/are
        emoji: `str | None`
            the emoji which triggers the board
            NOTE: If it's None, all boards of the guild will be removed

        Returns:
        -------
        List[Dict[str, Any]] :
            the deleted board records
        """
        table = Table("board.boards")
        columns = ["guild_id"]
        where: List[str | int] = [guild_id]
        if emoji:
            columns.append("emoji")
            where.append(emoji)

        records = await table.delete(columns=columns, matching_values=where)
        if records:
            cls._cache_remove_guild(guild_id)
        return records

    @classmethod
    async def add_reaction(
        cls,
        guild_id: int,
        message_id: int,
        reacter_id: int,
        emoji: str,
    ):
        """
        Adds a reaction

        Args:
        -----
        guild_id : `int`
            the guild_id of the message
        message_id : `int`
            the message_id of the reaction
        reacter_id : `int`
            the id of the person who added the reaction
        emoji : `str`
            the emoji which was added to the message
        """
        table = Table("board.reactions")
        await table.insert(
            which_columns=["message_id", "reacter_id", "emoji"],
            values=[message_id, reacter_id, emoji]
        )
        cls._cache_add_entry(guild_id, emoji, message_id)

    @classmethod
    async def remove_reaction(
        cls,
        guild_id: int,
        message_id: int,
        reacter_id: int,
        emoji: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Delete reaction(s)

        Args:
        -----
        message_id: `int`
            the message_id of the reaction
        emoji: `str | None`
            the emoji which was removed from the message
            NOTE: If it's None, all reactions of the reacter of the message will be deleted

        Returns:
        -------
        List[Dict[str, Any]] :
            Deleted records
        """
        table = Table("board.reactions")
        columns = ["message_id", "reacter_id"]
        where: List[str | int] = [message_id, reacter_id]
        if emoji:
            columns.append("emoji")
            where.append(emoji)
        records = await table.delete(columns=columns, matching_values=where)
        for r in records:
            cls._cache_remove_entry(guild_id, r["emoji"], message_id)
        return records

    @classmethod
    async def fetch_entry_reaction_amount(
        cls,
        original_message_id: int,
        emoji: str,
    ) -> int:
        """
        Returns:
        -------
        int :
            how many reactions are currently added to this entry
        """
        table = Table("board.reactions")
        record = (await table.execute(
            (
                f"SELECT COUNT(*) AS count\n"
                f"FROM {table.name}\n"
                f"WHERE message_id = $1 and emoji = $2"
            ),
            original_message_id,
            emoji
        ))[0]
        return record["count"]
    
    @classmethod
    async def fetch_all_entries(
        cls,
    ) -> List[Dict[str, Any]]:
        """
        Returns:
        -------
        List[Dict[str, Any]] :
            all entries
        """
        table = Table("board.entries")
        return await table.fetch(
            f"SELECT * FROM {table.name}"
        )


    