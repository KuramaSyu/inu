import traceback
from typing import *
import json
import logging
import datetime
from datetime import timedelta, timezone
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
from ..poll import Poll

from core import getLogger, Table

log = getLogger(__name__)


# the time in seconds, after the next sql statement, to get further reminders, will be executed
POLL_SYNC_TIME = 5*60

class PollManager:
    bot: Inu
    db: Database
    active_polls: Set[Poll]
    polls: Table

    @classmethod
    async def remove_poll(cls, poll: Poll):
        """remove poll from db"""
        ...
    
    @classmethod
    async def add_poll(cls, poll: Poll):
        """add poll to db"""
        #cls.polls.upsert(which_columns, values)
        ...
    
    @classmethod
    async def init_bot(cls, bot: Inu):
        cls.bot = bot
        cls.db = bot.db
        cls.polls = Table("polls")
        # sync polls from db 
