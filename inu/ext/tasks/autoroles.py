from typing import *
import asyncio
import logging
from datetime import datetime, timedelta

import lightbulb
from lightbulb.commands.base import OptionModifier as OM
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger

from utils import AutoroleManager, AutoroleAllEvent
from core import Table, getLogger, Inu

log = getLogger(__name__)
METHOD_SYNC_TIME: int = 60*5
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
    await method()

    trigger = IntervalTrigger(seconds=METHOD_SYNC_TIME)
    plugin.bot.scheduler.add_job(method, trigger)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    await init_method()

async def init_method():
    pass

async def method():
    pass

@plugin.listener(hikari.MemberCreateEvent)
async def on_member_join(event: hikari.MemberCreateEvent):
    """used to call the default role callback"""
    events = await AutoroleManager.fetch_events(event.guild_id, AutoroleAllEvent)
    log.debug(f"found {len(events)} events for guild {event.guild_id}")
    tasks: List[asyncio.Task] = []
    for task in events:
        tasks.append(asyncio.create_task(task.callback(event)))
    await asyncio.gather(*tasks)


def load(inu: Inu):
    global bot
    bot = inu
    inu.add_plugin(plugin)