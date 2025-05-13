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
import lightbulb.utils as lightbulb_utils
from lightbulb import Context, SlashCommand, invoke
import hikari
from numpy import isin
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger

from utils.db.reminders import REMINDER_UPDATE, Reminders
from utils import HikariReminder, Human, Paginator, crumble
from core import Table, Inu, InuContext


from core import getLogger


log = getLogger(__name__)

loader = lightbulb.Loader()
bot: Inu = Inu.instance

async def fetch_hour_offset(id: int):
    table = Table("guild_timezones")
    r = await table.select(["guild_or_author_id"], [id])
    try:
        return r[0]["offset_hours"]
    except IndexError:
        return 0

@loader.error_handler
async def handler(exc: lightbulb.exceptions.ExecutionPipelineFailedException) -> bool:
    ctx = exc.context
    if isinstance(exc.causes[0], RuntimeError):
        with open("inu/data/text/reminder-help.txt", "r", encoding="utf-8") as f:
            txt = f.read()
        log.warning(f"Error in reminder command: {traceback.format_exc()}")
        await ctx.respond(f"{txt}")
        return True
    else:
        return False
    
    

@loader.command
class Remind(
    SlashCommand,
    name="remind",
    description="set a reminder",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL]
):
    info = lightbulb.string(
        "info",
        "the waiting time, continued by the text you want to be reminded",
    )

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        message_id = 0
        if ctx.message_id:
            message_id = ctx.message_id
        offset_hours = await fetch_hour_offset(ctx.guild_id or ctx.author.id)
        reminder = HikariReminder(
            ctx.channel_id,
            ctx.author.id,
            message_id,
            self.info,
            ctx,
            offset_hours=offset_hours,
        )
        await ctx.respond(
            f"Reminding you on: <t:{str(int(reminder.datetime.timestamp()))}>\n"\
            f"or in seconds: `{Human.number(round(reminder.in_seconds, 2))}`"
        )

reminder_group = lightbulb.Group(name="reminder", description="Group with options for reminders")

@reminder_group.register
class ReminderList(
    SlashCommand,
    name="list",
    description="Get a list with all your reminders",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL]
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
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

@reminder_group.register
class ReminderCancel(
    SlashCommand,
    name="cancel",
    description="cancel a reminder",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL]
):
    reminder_id = lightbulb.integer("id", "The id (get it with reminder list) of the reminder")

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        record = await Reminders.delete_reminder_by_id(int(self.reminder_id))
        if not record:
            await ctx.respond(f"I would do it, but there is no reminder with id {self.reminder_id}")
        elif record["creator_id"] != ctx.author.id:
            await ctx.respond(f"_YOU_ haven't a reminder with that id. So I won't cancel it!")
        else:
            await ctx.respond(f"Reminder is canceled :)")

loader.command(reminder_group)
