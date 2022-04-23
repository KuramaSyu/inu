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

plugin = lightbulb.Plugin("Update qalc", "Sends daily automated Reddit pictures")

async def update_qalc_currency():
    #log.debug("Updating qalc currency")
    await Bash.execute(["qalc", "-e", "1+1"])
    #log.debug(f"{s=};{e=}")

# @plugin.listener(ShardReadyEvent)
# async def load_tasks(event: ShardReadyEvent):
#     try:
#         log.debug("add scheduler job to update currency")
#         trigger = IntervalTrigger(days=1)
#         bot: Inu = plugin.bot
#         bot.scheduler.add_job(update_qalc_currency, trigger)
#         log.debug("update qalc currency")
#         await update_qalc_currency()
#     except:
#         log.error(traceback.format_exc())

def load(bot: Inu):
    bot.add_plugin(plugin)