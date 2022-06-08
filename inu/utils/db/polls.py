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

from core.bot import Inu
from core import Database, Table
#from ..poll import Poll

from core import getLogger, Table

log = getLogger(__name__)


# the time in seconds, after the next sql statement, to get further reminders, will be executed
POLL_SYNC_TIME = 5*60

class PollManager:
    bot: Inu
    db: Database
    active_polls: Set["Poll"]

    @classmethod
    async def init_bot(cls, bot: Inu):
        cls.bot = bot
        cls.db = bot.db
        cls.active_polls = set()
        
        # sync polls from db

    @classmethod
    def get_poll(cls, message_id: int, channel_id: int) -> Optional["Poll"]:
        for poll in cls.active_polls:
            if poll.message_id == message_id and poll.channel_id == channel_id:
                return poll
        return None

    @classmethod
    async def add_poll(cls, poll: "Poll") -> Optional[int]:
        cls.active_polls.add(poll)
        if datetime.now() + timedelta(minutes=10) > poll._active_until:
            # run local without db
            # call Poll.finish()
            pass
        else:
            # add to db
            pass
        return None

    
    @classmethod
    async def _db_add_poll(cls, poll: "Poll") -> int:
        """add poll to db. returns poll id"""
        table = Table("polls")
        return await table.insert(
            which_columns=[
                "guild_id", "message_id", "channel_id", 
                "creator_id", "title", "description", 
                "expires", "type"
            ],
            values=[
                poll._guild_id, poll._message_id, poll._channel_id,
                poll._creator_id, poll._title, poll._description,
                poll._active_until, poll.kind
            ],
            returning="poll_id"
        )

    @classmethod
    async def remove_poll(cls, poll: "Poll"):
        """remove poll from db"""
        table = Table("polls")
        await table.delete(
            columns=["poll_id"],
            matching_values=[poll.id]
        )

    @classmethod
    async def add_vote(cls, poll_id: int, user_id: int, option_id: str):
        table = Table("poll_votes")
        await table.insert(which_columns=["poll_id", "option_id", "user_id"], values=[poll_id, option_id, user_id])

    @classmethod
    async def remove_vote(cls, poll_id: int, user_id: int, option_id: str):
        table = Table("poll_votes")
        await table.delete(columns=["poll_id", "user_id", "option_id"], matching_values=[poll_id, user_id, option_id])

    @classmethod
    async def add_poll_option(cls, poll_id: int, option_name: str, description: str) -> int:
        table = Table("poll_options")
        return await table.insert(
            which_columns=["poll_id", "name", "description"], 
            values=[poll_id, option_name, description],
            returning="option_id"
        )


    @classmethod
    async def remove_poll_options(cls, option_ids: List[int]):
        table = Table("poll_options")
        await table.delete(columns=["option_id"], matching_values=option_ids)

    @classmethod
    async def add_polls_to_set(cls, records: List[Mapping[str, Any]]):
        from utils import Poll
        for record in records:
            try:
                poll = Poll.from_record(record)
                cls.active_polls.add(poll)
            except Exception as e:
                log.error(f"could not load poll: {e}")
                log.error(traceback.format_exc())
