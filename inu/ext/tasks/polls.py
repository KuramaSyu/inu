import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging
from datetime import datetime, timedelta
import time

import lightbulb
from lightbulb.commands.base import OptionModifier as OM
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils import POLL_SYNC_TIME, PollManager, Poll

from core import Table, getLogger

log = getLogger(__name__)


plugin = lightbulb.Plugin("poll loader", "loads polls from database")

@plugin.listener(hikari.ShardReadyEvent)
async def load_tasks(event: hikari.ShardReadyEvent):
    await asyncio.sleep(3)
    await load_active_polls()

    trigger = IntervalTrigger(seconds=POLL_SYNC_TIME)
    plugin.bot.scheduler.add_job(load_active_polls, trigger)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)


async def load_active_polls():
    sql = """
    SELECT * FROM polls 
    WHERE expires < $1
    """
    poll_table = Table("polls")
    option_table = Table("poll_options")
    vote_table = Table("poll_votes")
    records_polls = await poll_table.fetch(sql, datetime.now() + timedelta(seconds=POLL_SYNC_TIME))

    #load
    for poll_record in records_polls:
        await PollManager.add_poll(await Poll.from_record(poll_record, plugin.bot))
        log.debug(f"Loaded poll: {poll_record['poll_id']} | expires: {poll_record['expires']}")

def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)