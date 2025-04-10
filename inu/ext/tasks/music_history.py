
from typing import *
import asyncio
import logging
from datetime import datetime, timedelta

import lightbulb
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger

from core import Table, getLogger, Inu
from utils import MusicHistoryHandler

log = getLogger(__name__)
METHOD_SYNC_TIME: int = 12*60*60 # 12 hours
SYNCING = False
bot: Inu = Inu.instance

plugin = lightbulb.Loader()

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
    await method()

async def method():
    await MusicHistoryHandler.clean()
