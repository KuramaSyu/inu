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

from core import Table, getLogger, Inu

log = getLogger(__name__)
SYNCING = False
bot: Inu

plugin = lightbulb.Plugin("poll loader", "loads polls from database")

@plugin.listener(hikari.ShardReadyEvent)
async def load_tasks(event: hikari.ShardReadyEvent):
    global SYNCING
    if SYNCING:
        return
    else:
        SYNCING = True
    await asyncio.sleep(3)
    await load_active_polls()

    trigger = IntervalTrigger(seconds=POLL_SYNC_TIME)
    plugin.bot.scheduler.add_job(load_active_polls, trigger)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)


async def load_active_polls():
    async def create_poll(poll_record: dict):
        poll = await Poll.from_record(poll_record, bot)
        await PollManager.add_poll(poll)

    sql = """
    SELECT * FROM polls 
    WHERE expires < $1
    """
    loaded_poll_count = 0
    poll_table = Table("polls")
    records_polls = await poll_table.fetch(sql, datetime.now() + timedelta(seconds=POLL_SYNC_TIME))

    #load polls and fetch further information
    start = datetime.now()
    tasks = []
    for poll_record in records_polls:
        task = asyncio.create_task(create_poll(poll_record))
        tasks.append(task)
        loaded_poll_count += 1
    if tasks:
        await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
    log.info(f"Loaded {loaded_poll_count} polls in {datetime.now() - start}")

def load(inu: Inu):
    global bot
    bot = inu
    inu.add_plugin(plugin)