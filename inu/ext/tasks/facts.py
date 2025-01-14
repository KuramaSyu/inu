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
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils import Facts

from core import Table, getLogger, Inu

log = getLogger(__name__)
METHOD_SYNC_TIME: int = 60*5
SYNCING = False
ENABLE = False
bot: Inu = Inu.instance
plugin = lightbulb.Loader()
METHOD_SYNC_TIME = bot.conf.commands.poll_sync_time


if ENABLE:
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
        bot.scheduler.add_job(method, trigger)
        logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
        await init_method()

    async def init_method():
        pass

    i = 0
    fetched_unique: List[int] = [0, 0]
    async def method():
        global i, fetched_unique
        await Facts._fetch_from_rest()
        await asyncio.sleep(5)
        fetched_unique[0] += Facts.last_metrics['from']
        fetched_unique[1] += Facts.last_metrics['unique']
        i += 1
        if i >= 20:
            log.debug(f"Fetched Facts - unique: {Facts.last_metrics['unique']}/{Facts.last_metrics['from']}")
            fetched_unique = [0,0]
            i = 0


    @plugin.listener(hikari.GuildReactionAddEvent)
    async def on_reaction_add(event: hikari.GuildReactionAddEvent):
        # insert to starboard
        ...

    @plugin.listener(hikari.GuildReactionDeleteEvent)
    async def on_reaction_remove(event: hikari.GuildReactionDeleteEvent):
        # delete from starboard
        ...

    @plugin.listener(hikari.GuildMessageDeleteEvent)
    async def on_message_remove(event: hikari.GuildMessageDeleteEvent):
        # delete from starboard
        ...

    @plugin.listener(hikari.GuildLeaveEvent)
    async def on_guild_leave(event: hikari.GuildLeaveEvent):
        # remove all starboards
        ...

