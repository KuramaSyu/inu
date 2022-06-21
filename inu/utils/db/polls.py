from __future__ import annotations
import traceback
from typing import *
import json
import logging
from datetime import timedelta, timezone, datetime
import asyncio
from enum import Enum
import time
import re

import hikari
from hikari.impl import ActionRowBuilder
from hikari.embeds import Embed
import lightbulb
from lightbulb.context import Context
import asyncpg
import pandas

from core.bot import Inu
from core import Database, Table
from core import getLogger, Table

if TYPE_CHECKING:
    from utils import Poll

log = getLogger(__name__)


# the time in seconds, after the next sql statement, to get further reminders, will be executed
POLL_SYNC_TIME = 5*60

class PollManager:
    bot: Inu
    db: Database
    message_id_cache: Set[int] = set()

    @classmethod
    async def init_bot(cls, bot: Inu):
        cls.bot = bot
        cls.db = bot.db
        loaded_poll_count = 0
        global POLL_SYNC_TIME
        POLL_SYNC_TIME = bot.conf.commands.poll_sync_time
        await cls.delete_old_polls()
        
    @classmethod
    async def delete_old_polls(cls):
        sql = (
            "DELETE FROM polls "
            "WHERE expires < $1"
        )
        table = Table("polls")
        records = await table.fetch(sql, datetime.now())
        for record in records:
            cls.message_id_cache.remove(record["message_id"])
        log.info(f"Deleted {len(records)} old polls")
        

    @classmethod
    async def fetch_poll(cls, message_id: int) -> Optional[Mapping[str, Any]]:
        sql = (
            "SELECT * FROM polls "
            "WHERE message_id = $1"
        )
        try:
            return (await (Table("polls")).fetch(sql, message_id))[0]
        except IndexError:
            return None

    @classmethod
    async def fetch_option_id(cls, poll_id: int, reaction_str: str):
        sql = (
            "SELECT option_id FROM poll_options\n "
            "WHERE poll_id = $1 AND reaction = $2"
        )
        try:
            option_id = (await (Table(
                "poll_options"
            )).fetch(
                sql, 
                poll_id, 
                reaction_str
            )
            )[0]["option_id"]
        except IndexError:
            return None
        return option_id

    @classmethod
    async def add_poll(
        cls,
        guild_id: int,
        message_id: int,
        channel_id: int,
        creator_id: int,
        title: str,
        description: str,
        poll_type: int,
        starts: Optional[datetime] = None,
        expires: Optional[datetime] = None,
        anonymous: bool = False,
    ) -> Optional[Mapping[str, Any]]:
        """add poll to db. returns poll id"""

        table = Table("polls")

        sql = """
            INSERT INTO polls ( 
                guild_id, message_id, channel_id, creator_id, 
                starts, title, description, expires, poll_type, anonymous 
            )
            VALUES ( $1, $2, $3, $4, $5, $6, $7, $8, $9, $10 )
            RETURNING *
        """
        # return values -> List[Dataset["poll_id"]]
        
        record = (await table.execute(
            sql, 
            guild_id, message_id, channel_id, 
            creator_id, starts, title, 
            description, expires, 
            poll_type, anonymous
        ))[0]
        cls.message_id_cache.add(message_id)
        return record

    @classmethod
    async def remove_poll(cls, poll_id: int, message_id: int):
        """remove poll from db"""
        table = Table("polls")
        await table.delete(
            columns=["poll_id"],
            matching_values=[poll_id]
        )
        cls.message_id_cache.remove(message_id)

    @classmethod
    async def add_vote(cls, poll_id: int, user_id: int, option_id: str):
        table = Table("poll_votes")
        await table.insert(which_columns=["poll_id", "option_id", "user_id"], values=[poll_id, option_id, user_id])

    @classmethod
    async def remove_vote(cls, poll_id: int, user_id: int):
        table = Table("poll_votes")
        await table.delete(columns=["poll_id", "user_id"], matching_values=[poll_id, user_id])

    @classmethod
    async def add_poll_option(cls, poll_id: int, reaction: str, description: str) -> int:
        table = Table("poll_options")
        return await table.insert(
            which_columns=["poll_id", "reaction", "description"], 
            values=[poll_id, reaction, description],
            returning="option_id"
        )

    @classmethod
    async def fetch_options(cls, poll_id: int) -> List[Mapping[str, Any]]:
        table = Table("poll_options")
        return await table.fetch(
            (
                "SELECT * FROM poll_options "
                "WHERE poll_id = $1"
            ), poll_id
        )

    @classmethod
    async def fetch_votes(cls, poll_id: int) -> List[Mapping[str, Any]]:
        table = Table("poll_votes")
        return await table.fetch(
            (
                "SELECT * FROM poll_votes "
                "WHERE poll_id = $1"
            ), poll_id
        )
    # # guild_id BIGINT NOT NULL,
    # # game VARCHAR(100),
    # # user_amount BIGINT NOT NULL,
    # # timestamp TIMESTAMP,
    # # PRIMARY KEY (guild_id, game, timestamp)
    @classmethod
    async def sync_long_time_games(cls, when_older_than: datetime):
        ...
        # fetch relevant records form current games
        table = Table("current_games")
        sql = (
            f"SELECT * FROM {table.name}"
            ""
        )
        df = table.execute(sql, when_older_than)
        table = Table("long_time_games")
        #values = 
        sql =(
            f"INSERT INTO {table.name} (guild_id, game, user_amount, timestamp)"
            f"VALUES ()()()"
            f"ON CONFLICT (guild_id, game, timestamp) DO UPDATE"
            f"SET user_amount = user_amount + $1"
        )

        # USE MERGE
        # WITH new_values (guild_id::BIGINT, game::VARCHAR(100), user_amount::INTEGER, timestamp::TIMESTAMP) AS (
        #   VALUES 
        #      $1
        # ),
        # upsert AS ( 
        #     UPDATE long_time_games lt_games
        #         SET user_amount = user_amount + nv.user_amount
        #     FROM new_values nv
        #     WHERE lt_games.guild_id = nv.guild_id AND lt_games.game = nv.game AND lt_games.timestamp = nv.timestamp
        #     RETURNING lt_games.*
        # )
        # INSERT INTO long_time_games (guild_id, game, user_amount, timestamp)
        # SELECT guild_id, game, user_amount, timestamp
        # FROM new_values
        # WHERE NOT EXISTS (SELECT 1 
        #                   FROM upsert up 
        #                   WHERE up.date = new_values.date
        #                   AND up.customer_fk = new_values.customer_fk)


        # resample to 1d (code from inu/commands/statistics)
        # upsert with addition in column amount

