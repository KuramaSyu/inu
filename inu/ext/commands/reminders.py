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
import lightbulb.utils as lightbulb_utils
from lightbulb import commands, context
from lightbulb.commands.base import OptionModifier as OM
import hikari
from numpy import isin
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils.reminders import Reminders

from utils import HikariReminder, Human


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


plugin = lightbulb.Plugin("Basics", "Extends the commands with basic commands", include_datastore=True)
        

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
    await ctx.respond(f"reminding you to: {str(reminder.datetime)}\nSeconds: {Human.number(reminder.in_seconds)}")


def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)
