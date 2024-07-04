import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging
import datetime as d
from datetime import datetime
import time
import traceback

from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari import ButtonStyle, PartialMessage
from hikari.impl.special_endpoints import MessageActionRowBuilder
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

from utils.db.reminders import REMINDER_UPDATE, Reminders
from utils import HikariReminder, Human, Paginator, crumble
from core import Table


from core import getLogger


log = getLogger(__name__)

plugin = lightbulb.Plugin("Basics", "Extends the commands with basic commands", include_datastore=True)

        

@plugin.command
@lightbulb.add_cooldown(300, 3, lightbulb.UserBucket)
@lightbulb.option(
    "info", 
    "the waiting time, continued by the text you want to be reminded", 
    type=str, 
    modifier=OM.CONSUME_REST,
)
@lightbulb.command("remind", "set a reminder", aliases=["timer"])
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def create_reminder(ctx: context.Context):
    message_id = 0
    if hasattr(ctx.event, "message_id"):
        message_id = ctx.event.message_id
    offset_hours = await fetch_hour_offset(ctx.guild_id or ctx.author.id)
    reminder = HikariReminder(
        ctx.channel_id,
        ctx.author.id,
        message_id,
        ctx.options.info,
        ctx,
        offset_hours=offset_hours,
    )
    await ctx.respond(
        f"reminding you to: <t:{str(int(reminder.datetime.timestamp()))}>\n"\
        f"or in seconds: `{Human.number(round(reminder.in_seconds, 2))}`"
    )

@create_reminder.set_error_handler
async def on_reminder_error(event: CommandErrorEvent):
    
    with open("inu/data/text/reminder-help.txt", "r", encoding="utf-8") as f:
        txt = f.read()
    log.warning(f"Error in reminder command: {traceback.format_exc()}")
    if event.context.options.info is None:
        await event.context.respond(txt)
    else:
        await event.context.respond(f"I am not a fucking trash converter 🖕\n\n{txt}")
    return True

async def fetch_hour_offset(id: int):
    table = Table("guild_timezones")
    r = await table.select(["guild_or_author_id"], [id])
    try:
        return r[0]["offset_hours"]
    except IndexError:
        return 0

@plugin.command
@lightbulb.command("reminder", "Group with options for reminders")
@lightbulb.implements(commands.SlashCommandGroup, commands.PrefixCommandGroup)
async def reminder(ctx: context.Context):
    pass

@reminder.child
@lightbulb.add_cooldown(300, 8, lightbulb.UserBucket)
@lightbulb.command("list", "Get a list with all your reminders")
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def reminder_list(ctx: context.Context):
    table = Table("reminders")
    records = await table.select(
        columns=["creator_id"],
        matching_values=[ctx.author.id],
        order_by="remind_time ASC"
    )
    if records is None:
        await ctx.respond("There are no upcoming reminders")
        return
    msg = f"**{ctx.author.username}'s reminders**\n\n>>> "
    for r in records:
        msg += (
            f"ID: {r['reminder_id']} "
            f"<t:{int(r['remind_time'].timestamp())}:R> <t:{int(r['remind_time'].timestamp())}>\n"
        )
        if r["remind_text"]:
            msg += f"``` {Human.short_text(r['remind_text'], 70)} ```"
        msg += "\n\n"
    pag = Paginator(page_s=crumble(msg))
    await pag.start(ctx)

@reminder.child
@lightbulb.add_cooldown(300, 5, lightbulb.UserBucket)
@lightbulb.option("id", "The id (get it with reminder list) of the reminder", type=int)
@lightbulb.command("cancel", "cancel a reminder", aliases=["delete"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def reminder_cancel(ctx: context.Context):
    record = await Reminders.delete_reminder_by_id(int(ctx.options.id))
    if not record:
        await ctx.respond(f"I would do it, but there is no reminder with id {ctx.options.id}")
    elif record["creator_id"] != ctx.author.id:
        await ctx.respond(f"_YOU_ haven't a reminder with that id. So I won't cancel it!")
    else:
        await ctx.respond(f"Reminder is canceled :)")

def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)
