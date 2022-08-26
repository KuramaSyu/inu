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
import traceback

import lightbulb
from lightbulb.commands.base import OptionModifier as OM
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils import PollManager, Poll

from core import Table, getLogger, Inu

log = getLogger(__name__)
POLL_SYNC_TIME: int
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
    await initial_load_all_polls()

async def initial_load_all_polls():
    sql = """
    SELECT * FROM polls 
    """
    loaded_poll_count = 0
    poll_table = Table("polls", debug_log=False)
    records_polls = await poll_table.fetch(sql)
    count = 0
    for record in records_polls:
        count += 1
        PollManager.message_id_cache.add(record["message_id"])
    log.info(f"Added {count} polls to cache")

    sql = """
    DELETE FROM polls
    WHERE expires < $1
    """
    await poll_table.execute(sql, datetime.now())


async def load_active_polls():
    try:
        async def create_poll(poll_record: dict):
            poll = await Poll.from_record(poll_record, bot)
            await PollManager.add_poll(poll)

        sql = """
        SELECT * FROM polls 
        WHERE expires < $1
        """
        loaded_poll_count = 0
        poll_table = Table("polls", debug_log=False)
        records_polls = await poll_table.fetch(sql, datetime.now() + timedelta(seconds=POLL_SYNC_TIME))

        #load polls and fetch further information
        for poll_record in records_polls:
            asyncio.create_task((Poll(poll_record, bot)).finalize())
    except Exception as e:
        log.error(traceback.format_exc())
        



# async def initialize_all_polls():
#     sql = """DELETE FROM polls WHERE expires < $1"""
#     await Table("polls").fetch(sql, datetime.now())

#     sql = """SELECT * FROM polls"""
#     records = await Table("polls").fetch(sql)

def load(inu: Inu):
    global bot
    bot = inu
    global POLL_SYNC_TIME
    POLL_SYNC_TIME = inu.conf.commands.poll_sync_time
    inu.add_plugin(plugin)