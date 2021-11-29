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
import logging
import enum

import asyncpg
from asyncache import cached
from cachetools import TTLCache, LRUCache
import hikari
from hikari import User, Member
from numpy import column_stack


from .db import Database

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class Columns(enum.Enum):
    CHANNEL_IDS = "channel_ids"
    TOP_CHANNEL_IDS = "top_channel_ids"

class DailyContentChannels:
    db: Database
    
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @classmethod
    def set_db(cls, database: Database):
        cls.db = database

    @classmethod
    async def add_channel(
        cls,
        table_column: Columns,
        channel_id: int,
        guild_id: int,
    ):
        """
        Adds the <channel_id> to the channels, where my bot sends frequently content to

        Args:
        -----
            - table_column: (`~.Columns`) Enum for options
            - channel_id: (int) the channel_id
            - guild_id: (int) the id of the guild where the channel is in

        Note:
        -----
            - if the channel_id is already in the list for guild_id, than the channel_id wont be added to it
        
        """
        log.info(f"add channel {channel_id=}, {guild_id=}")
        sql = """
        SELECT * FROM reddit_channels
        WHERE guild_id = $1
        """
        record = await cls.db.row(sql, guild_id)
        if record is None:
            channels = [channel_id]
            sql = f"""
            INSERT INTO reddit_channels (guild_id, {table_column.value})
            VALUES ($1, $2)
            """
        else:
            channels = record[table_column.value]
            if not channels:
                channels = []
            channels.append(channel_id)
            channels = list(set(channels))  # remove duplicates
            sql = f"""
            UPDATE reddit_channels
            SET {table_column.value} = $2
            WHERE guild_id = $1
            """
        await cls.db.execute(sql, guild_id, channels)

    @classmethod
    async def remove_channel(
        cls,
        table_column: Columns,
        channel_id: int,
        guild_id: int,
    ):
        """
        Removes the <channel_id> from the channels, where my bot sends frequently content to

        Args:
        -----
            - table_column: (`~.Columns`) Enum for options
            - channel_id: (int) the channel_id
            - guild_id: (int) the id of the guild where the channel is in      
        """
        sql = """
        SELECT * FROM reddit_channels
        WHERE guild_id = $1
        """
        record = await cls.db.row(sql, guild_id)
        if record is None:
            return
        else:
            channels = record[table_column.value]
            try:
                channels.remove(channel_id)
            except ValueError:
                return
            sql = f"""
            UPDATE reddit_channels
            SET {table_column.value} = $1
            WHERE guild_id = $2
            """
            await cls.db.execute(sql, channels, guild_id)

    @classmethod
    async def get_channels_from_guild(
        cls,
        table_column: Columns,
        guild_id: int,
    ):
        """
        UNFINISHED
        Removes the <channel_id> from the channels, where my bot sends frequently content to

        Args:
        -----
            - table_column: (`~.Columns`) Enum for options
            - channel_id: (int) the channel_id
            - guild_id: (int) the id of the guild where the channel is in      
        """
        sql = """
        SELECT * FROM reddit_channels
        WHERE guild_id = $1
        """
        record = await cls.db.row(sql, guild_id)
        return record[table_column.value]

    @classmethod
    async def get_all_channels(
        cls,
        table_column: Columns,
    ) -> List[Dict[int, List[int]]]:
        """
        Returns:
        --------
            - table_column: (`~.Columns`) Enum for options
            - (List[Dict[int, List[int]]]) a list with dicts mapping from guild_id to a list of channel ids
        """
        sql = """
        SELECT * FROM reddit_channels
        """
        records = await cls.db.fetch(sql)
        if not records:
            return []
        mappings = []
        for r in records:
            channels = r[table_column.value]
            if channels is None: 
                continue
            mapping = {r["guild_id"]: channels}
            mappings.append(mapping)
        return mappings

