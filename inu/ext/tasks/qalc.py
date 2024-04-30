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
i = 0

async def update_qalc_currency():
    global i
    # -e = updating currency
    result = await Bash.execute(["qalc", "-t", "-e", "x EUR = 1 BTC"])
    i += 1
    if i % 5 == 0:
        log.info(f"Updated qalculate currencies ({i}th time)", prefix="Cache")
    else:
        log.debug(f"Updated qalculate currencies", prefix="Cache")

@plugin.listener(ShardReadyEvent)
async def load_tasks(event: ShardReadyEvent):
    global loaded
    if loaded:
        return
    loaded = True
    try:
        hours = 3
        trigger = IntervalTrigger(hours=hours)
        log.info(f"scheduled job for updating currency every {hours} hours", prefix="init")
        bot: Inu = plugin.bot
        bot.scheduler.add_job(update_qalc_currency, trigger)
        
        await update_qalc_currency()
    except:
        log.error(traceback.format_exc())

def load(bot: Inu):
    bot.add_plugin(plugin)