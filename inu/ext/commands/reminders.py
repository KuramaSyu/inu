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

from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari.messages import ButtonStyle
from hikari.impl.special_endpoints import ActionRowBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
from lightbulb.commands import message
import lightbulb.utils as lightbulb_utils
from lightbulb import commands, context
from lightbulb.commands.base import OptionModifier as OM
import hikari
from numpy import isin
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger

from utils import HikariReminder


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

plugin = lightbulb.Plugin("Basics", "Extends the commands with basic commands", include_datastore=True)

reminders = set()

@plugin.listener(hikari.ShardReadyEvent)
async def load_tasks(event: hikari.ShardReadyEvent):
    trigger = IntervalTrigger(seconds=10)
    plugin.bot.scheduler.add_job(load_upcoming_reminders, trigger)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    trigger = IntervalTrigger(minutes=5)
    plugin.bot.scheduler.add_job(clean_up_reminder_set, trigger)

def clean_up_reminder_set():
    datetime_ = datetime.datetime.now()
    for r in reminders.copy():
        if r["remind_time"] < datetime_:
            reminders.remove(r)

async def load_upcoming_reminders():
    sql = """
    SELECT * FROM reminders
    WHERE remind_time < $1
    """
    timestamp = datetime.datetime.fromtimestamp((time.time() + (4.25 * 60)))
    records = await plugin.bot.db.fetch(
        sql,
        timestamp,
    )
    for r in records:
        if r in reminders:
            continue
        reminders.add(r)
        reminder = HikariReminder(
            channel_id=r["channel_id"],
            creator_id=r["creator_id"],
            message_id=r["message_id"],
        )
        reminder.from_database(
            r["reminder_id"],
            r["remind_time"],
            r["remind_text"],
        )
    log.debug(reminders)
        

@plugin.command
@lightbulb.option(
    "info", 
    "the waiting time, continued by the text you want to be reminded", 
    type=str, 
    modifier=OM.CONSUME_REST
)
@lightbulb.command("remind", "set a reminder")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def create_reminder(ctx: context.Context):
    message_id = 0
    if hasattr(ctx.event, "message_id"):
        message_id = ctx.event.message_id
    reminder = HikariReminder(
        ctx.channel_id,
        ctx.author.id,
        message_id,
        ctx.options.info,
        ctx,
    )
    await ctx.respond(f"reminding you to: {str(reminder.datetime)}\nSeconds: {reminder.in_seconds}")


def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)
