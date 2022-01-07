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
import traceback

from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari.messages import ButtonStyle
from hikari.impl.special_endpoints import ActionRowBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
from lightbulb.commands import message
from lightbulb.events import CommandErrorEvent
import lightbulb.utils as lightbulb_utils
from lightbulb import commands, context
from lightbulb.commands.base import OptionModifier as OM
import hikari
from numpy import isin
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger

from utils.reminders import REMINDER_UPDATE, Reminders
from utils import HikariReminder, Human, Table


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

plugin = lightbulb.Plugin("Basics", "Extends the commands with basic commands", include_datastore=True)

        

@plugin.command
@lightbulb.option(
    "info", 
    "the waiting time, continued by the text you want to be reminded", 
    type=str, 
    modifier=OM.CONSUME_REST,
)
@lightbulb.command("remind", "set a reminder")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def create_reminder(ctx: context.Context):
    message_id = 0
    if hasattr(ctx.event, "message_id"):
        message_id = ctx.event.message_id
    offset_hours = await fetch_hour_offset(ctx.guild_id)
    log.debug(offset_hours)
    reminder = HikariReminder(
        ctx.channel_id,
        ctx.author.id,
        message_id,
        ctx.options.info,
        ctx,
        offset_hours=offset_hours,
    )
    await ctx.respond(f"reminding you to: <t:{str(int(reminder.datetime.timestamp()))}>\nor in seconds: `{Human.number(reminder.in_seconds)}`")

#@create_reminder.set_error_handler
async def on_reminder_error(event: CommandErrorEvent):
    with open("inu/data/text/reminder-help.txt", "r", encoding="utf-8") as f:
        txt = f.read()
    await event.context.respond(f"I am not a fucking trash converter 🖕\n\n{txt}")
    return True

async def fetch_hour_offset(guild_id: int):
    table = Table("guild_timezones")
    r = await table.select(["guild_id"], [guild_id])
    log.debug(r)
    return r[0]["offset_hours"]

def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)
