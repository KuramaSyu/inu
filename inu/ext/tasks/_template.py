
from typing import *
import asyncio
import logging
from datetime import datetime, timedelta

import lightbulb
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger

from core import Table, getLogger, Inu

log = getLogger(__name__)
METHOD_SYNC_TIME: int = 0
SYNCING = False
bot: Inu = Inu.instance  # directly instanciate the bot
METHOD_SYNC_TIME = bot.conf.commands.xxxx_time  # laod time from config
plugin = lightbulb.Loader()  # Plugin -> Loader

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

async def method():
    pass

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
