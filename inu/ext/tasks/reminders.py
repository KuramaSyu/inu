import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging
import datetime
import time

import lightbulb
from lightbulb.commands.base import OptionModifier as OM
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils import REMINDER_UPDATE, Reminders


plugin = lightbulb.Plugin("reminder loader", "loads reminders from database")

@plugin.listener(hikari.ShardReadyEvent)
async def load_tasks(event: hikari.ShardReadyEvent):
    await asyncio.sleep(3)
    await load_upcoming_reminders()

    trigger = IntervalTrigger(seconds=REMINDER_UPDATE)
    plugin.bot.scheduler.add_job(load_upcoming_reminders, trigger)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)

async def load_upcoming_reminders():
    sql = """
    SELECT * FROM reminders
    WHERE remind_time < $1
    """
    timestamp = datetime.datetime.fromtimestamp((time.time() + (REMINDER_UPDATE+10)))
    records = await plugin.bot.db.fetch(
        sql,
        timestamp,
    )
    Reminders.add_reminders_to_set(records)

# def load(bot: lightbulb.BotApp):
#     bot.add_plugin(plugin)