from enum import Enum
from datetime import datetime, timedelta
from typing import *

import asyncpg
asyncpg.UniqueViolationError

from core import Table, Inu


class BoardManager:
    bot: Inu
    # Mapping[guild_id, Dict]
    # Dict has keys emojis (str set) and message_ids (int set)
    # this cache is not aware of, that a message can have multiple reactions
    _cache: Dict[int, Dict[str, Set[int] | Set[str]]]

    @classmethod
    def _cache_add_entry(cls, guild_id: int, emoji: str, message_id: int):
        guild_cache = cls._cache.get(guild_id)
        if not guild_cache:
            cls._cache[guild_id] = {
                emoji: set()
            }
        elif guild_cache.get(emoji) is None:
            cls._cache[guild_id][emoji] = set()
        cls._cache[guild_id][emoji].add(emoji)  # type: ignore

    @classmethod
    def _cache_remove_entry(cls, guild_id: int, emoji: str, message_id: int):
        try:
            cls._cache[guild_id][emoji].remove(message_id)  # type: ignore
        except KeyError:
            pass

    @classmethod
    def _cache_remove_emoji(cls, guild_id: int, emoji: str):
        try:
            del cls._cache[guild_id][emoji]
        except KeyError:
            pass

    @classmethod
    def init_bot(cls, bot: Inu):
        cls.bot = bot

    @classmethod
    def has_emoji(cls, guild_id: int, emoji: str) -> bool:
        return bool(cls._cache.get(guild_id, {}).get(emoji))

    @classmethod
    def has_message_id(cls, guild_id: int, emoji:str, message_id: int) -> bool:
        return message_id in cls._cache.get(guild_id, {}).get(emoji, [])   

    @classmethod
    async def add_entry(
        cls,
        message_id: int,
        guild_id: int,
        emoji: str,
    ):
        """
        Raises
        ------
        asyncpg.UniqueViolationError:
            When this entry already exists. Should normally not occure
        """
        table = Table("board.reactions")
        await table.insert(
            which_columns=["message_id", "guild_id", "created_at", "emoji"],
            values=[message_id, guild_id, datetime.now(),emoji]
        )
        cls._cache_add_entry(guild_id, emoji, message_id)

    @classmethod
    async def remove_entry(
        cls,
        message_id: int,
        emoji: Optional[str] = None,
    ):
        """
        Delete board entries(s)

        Args:
        -----
        message_id: `int`
            the message_id which shouldn't be tracked by the board
        emoji: `str | None`
            the emoji which triggers the board
            NOTE: If it's None, all entries with this message id will be removed (since a message can have different reactions)
        """
        table = Table("board.reactions")
        columns = ["message_id"]
        where: List[str | int] = [message_id]
        if emoji:
            columns.append("emoji")
            where.append(emoji)
        a = ()
        records = await table.delete(columns=columns, matching_values=where)
        for r in records:
            cls._cache_remove_entry(r["guild_id"], r["emoji"], r["message_id"])

    @classmethod
    async def fetch_entry(
        cls,
        message_id: int
    ):
        pass

    @classmethod
    async def add_board(
        cls,
        guild_id: int,
        channel_id: int,
        emoji: str,
    ):
        table = Table("starboard.starboards")
        sql = (
            f"INSERT INTO {table.name} (guild_id, channel_id, entry_lifetime, emoji)"
            "VALUES ($1, $2, $3, $4)"
            "ON CONFLICT (guild_id)"
            "DO"
            "   UPDATE SET channel_id = $2"
        )
        await table.execute(
            sql, 
            guild_id, 
            channel_id, 
            timedelta(days=cls.bot.conf.commands.starboard_entry_lifetime)
        )

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
            f"SELECT {select} FROM {table.name}"
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
        channel_id: int,
        emoji: Optional[str] = None,
    ):
        """
        Delete starboard(s)

        Args:
        -----
        guild_id: `int`
            the guild_id where the board(s) is/are
        emoji: `str | None`
            the emoji which triggers the board
            NOTE: If it's None, all boards of the guild will be removed
        """
        table = Table("board.boards")
        columns = ["guild_id", "channel_id"]
        where: List[str | int] = [guild_id, channel_id]
        if emoji:
            columns.append("emoji")
            where.append(emoji)

        records = await table.delete(columns=columns, matching_values=where)
        for r in records:
            cls._cache_remove_emoji(guild_id, r["emoji"])

    @classmethod
    async def add_reaction(
        cls,
        guild_id: int,
        message_id: int,
        reacter_id: int,
        emoji: str,
    ):
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
    ):
        """
        Delete reaction(s)

        Args:
        -----
        message_id: `int`
            the message_id of the reaction
        emoji: `str | None`
            the emoji which was removed from the message
            NOTE: If it's None, all reactions of the reacter of the message will be deleted
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



    