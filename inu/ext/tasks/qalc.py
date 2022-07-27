import asyncio
import typing
from typing import *
import random
import datetime
import time as tm
import traceback
import logging
from pprint import pformat

import hikari
from hikari.events.shard_events import ShardReadyEvent
import lightbulb
from lightbulb import Plugin
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger

from utils import Reddit
from core.db import Database
from core import Inu
from utils import DailyContentChannels
from utils import Columns as Col


from core import getLogger, Bash

log = getLogger(__name__)
loaded = False

plugin = lightbulb.Plugin("Update qalc", "Sends daily automated Reddit pictures")

async def update_qalc_currency():
    # -e = updating currency
    result = await Bash.execute(["qalc", "-e", "x EUR = 1 BTC"])
    log.debug(f"Updated qalc currency")

@plugin.listener(ShardReadyEvent)
async def load_tasks(event: ShardReadyEvent):
    global loaded
    if loaded:
        return
    loaded = True
    try:
        log.info("scheduled job for updating currency")
        trigger = IntervalTrigger(hours=3)
        bot: Inu = plugin.bot
        bot.scheduler.add_job(update_qalc_currency, trigger)
        
        await update_qalc_currency()
    except:
        log.error(traceback.format_exc())

def load(bot: Inu):
    bot.add_plugin(plugin)