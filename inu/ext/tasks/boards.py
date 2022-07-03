"""
Handling that the boards are actually working:
    - adding reactions and messages to db
    - update board messages
    - remove boards when the bot leaves a guild
"""

import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging
from datetime import datetime, timedelta
import time
import traceback

import lightbulb
from lightbulb.commands.base import OptionModifier as OM
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils.db import BoardManager

from core import Table, getLogger, Inu

log = getLogger(__name__)
METHOD_SYNC_TIME: int
SYNCING = False
bot: Inu

plugin = lightbulb.Plugin("poll loader", "loads polls from database")

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
    plugin.bot.scheduler.add_job(method, trigger)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    await init_method()

async def init_method():
    pass

async def method():
    pass

async def update_message(
    message_id: int,
    emoji: str,
):
    # fetch information from db and recreate or delete message
    ...

@plugin.listener(hikari.GuildReactionAddEvent)
async def on_reaction_add(event: hikari.GuildReactionAddEvent):
    # insert to board

    # guild has no board with this reaction
    if not BoardManager.has_emoji(event.guild_id, event.emoji_name):
        return

    # board don't has this message -> create entry
    if not BoardManager.has_message_id(event.guild_id, event.emoji_name, event.message_id):
        await BoardManager.add_entry(
            message_id=event.message_id,
            guild_id=event.guild_id,
            emoji=event.emoji_name,
        )
    
    # add a reaction
    await BoardManager.add_reaction(
        guild_id=event.guild_id,
        message_id=event.message_id,
        reacter_id=event.user_id,
        emoji=event.emoji_name,
    )

    # method for updating a message in a board

@plugin.listener(hikari.GuildReactionDeleteEvent)
async def on_reaction_remove(event: hikari.GuildReactionDeleteEvent):
    # delete from board

    # guild has no board with this reaction
    if not BoardManager.has_emoji(event.guild_id, event.emoji_name):
        return

    # board don't has this message -> create entry
    if not BoardManager.has_message_id(event.guild_id, event.emoji_name, event.message_id):
        return
    try:
        await BoardManager.remove_reaction(
            guild_id=event.guild_id,
            message_id=event.message_id,
            reacter_id=event.user_id,
            emoji=event.emoji_name,
        )
    except Exception:
        log.waring(f"insertion error, which shouldn't occure.\n{traceback.format_exc()}")
    # TODO: when a message has no reactions any more, delete it 
    # (db will be cleared automatically -> when updating message results in error, delete message)

@plugin.listener(hikari.GuildMessageDeleteEvent)
async def on_message_remove(event: hikari.GuildMessageDeleteEvent):
    # delete from board
    ...

@plugin.listener(hikari.GuildLeaveEvent)
async def on_guild_leave(event: hikari.GuildLeaveEvent):
    # remove all boards
    ...

def load(inu: Inu):
    global bot
    bot = inu
    global METHOD_SYNC_TIME
    METHOD_SYNC_TIME = inu.conf.commands.poll_sync_time
    inu.add_plugin(plugin)