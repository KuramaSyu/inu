"""
Handling that the boards are actually working:
    - adding reactions and messages to db
    - update board messages
    - remove boards when the bot leaves a guild
"""

from typing import *
import asyncio
import logging
from datetime import datetime, timedelta
import time
import traceback

import lightbulb
from lightbulb.commands.base import OptionModifier as OM
import hikari
from hikari import Embed
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils.db import BoardManager
import asyncpg

from core import Table, getLogger, Inu
from utils import make_message_link, Colors

log = getLogger(__name__)
METHOD_SYNC_TIME: int
SYNCING = False
bot: Inu

plugin = lightbulb.Plugin("board tracker", "tracks messages if they where pinned")

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

@plugin.listener(hikari.GuildReactionAddEvent)
async def on_reaction_add(event: hikari.GuildReactionAddEvent):
    log.debug(f"receiving: {event.emoji_name}")
    # insert to board

    # guild has no board with this reaction
    if not BoardManager.has_emoji(event.guild_id, event.emoji_name):
        log.debug(f"emoji not tracked")
        return

    # board don't has this message -> create entry
    # if not BoardManager.has_message_id(event.guild_id, event.emoji_name, event.message_id):
    #     log.debug("board don't has this message -> create entry")
    #     await BoardManager.add_entry(
    #         message_id=event.message_id,
    #         guild_id=event.guild_id,
    #         emoji=event.emoji_name,
    #     )
    
    message: Optional[hikari.Message] = None
    entry = await BoardManager.fetch_entry(event.message_id, event.emoji_name)
    if not entry:
        log.debug(f"no entry found => add entry")
        message = await bot.rest.fetch_message(event.channel_id, event.message_id)
        attachment_urls = [a.url for a in message.attachments]
        if message is None:
            return
        content = message.content or ""
        # add first embed to content
        if len(message.embeds) > 0:
            if message.embeds[0].title:
                content += f"\n\n**{message.embeds[0].title}**"
            if message.embeds[0].description:
                content += f"\n{message.embeds[0].description}"
            if message.embeds[0].image:
                attachment_urls.append(message.embeds[0].image.url)

        if not message:
            log.debug("message not found")
            return
        # add entry
        entry = (await BoardManager.add_entry(
            guild_id=event.guild_id,
            message_id=event.message_id,
            author_id=message.author.id,
            channel_id=message.channel_id,
            emoji=event.emoji_name,
            content=content,
            attachment_urls=attachment_urls,
        ))[0]

    # add a reaction
    log.debug(f"{entry=}")
    log.debug("add a reaction to db")
    try:
        await BoardManager.add_reaction(
            guild_id=event.guild_id,
            message_id=event.message_id,
            reacter_id=event.user_id,
            emoji=event.emoji_name,
        )
    except asyncpg.UniqueViolationError:
        log.debug(f"Violation error - reaction was already added")
    await update_message(entry, message)




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
        log.warning(f"insertion error, which shouldn't occure.\n{traceback.format_exc()}")
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

async def update_message(
    board_entry: Dict[str, Any],
    message: Optional[hikari.Message] = None,
):
    channel_id = board_entry["channel_id"]
    message_id = board_entry["message_id"]
    guild_id = board_entry["guild_id"]
    content = board_entry["content"]
    emoji = board_entry["emoji"]

    author = await bot.mrest.fetch_member(guild_id, board_entry["author_id"])
    if not author:
        log.warning(f"no member with id {board_entry['author_id']} found")
        return

    message_votes = await BoardManager.fetch_reactions(message_id)
    board = await BoardManager.fetch_board(guild_id, emoji)

    color_stages = {
        n: color for n, color in zip(
            range(1,100),
            [
                "slateblue", "mediumslateblue",
                "mediumpurple", "blueviolet", "indigo",
                "darkorchid", "darkviolet", "mediumorchid",
                "purple", "darkmagenta", "mediumvioletred",
                "deeppink", "crimson"
            ]
        )
    }
    color = color_stages.get(len(message_votes), "crimson")
    reaction_content = f"{len(message_votes)}x {emoji}"
    embed = Embed()
    embed.set_author(
        name=f"{author.username}", 
        icon=author.display_avatar_url
    )
    embed.description = (
        f"[Jump to the message in <#{board_entry['channel_id']}>]"
        f"({make_message_link(guild_id, channel_id, message_id)})\n\n{content}"
    )
    # embed color -> how many stars
    embed.color = Colors.from_name(color)

    if not board_entry["board_message_id"]:
        # create new entry
        if not message:
            raise RuntimeError(
                "in update_message:\nif board entry gets created first time, a message musst be passed in"
            )
        kwargs = {
            "attachments": board_entry['attachment_urls'],
            "embed": embed,
            "content": reaction_content,
            "components": message.components,
            "channel": board['channel_id'],
        }

        board_message = await bot.rest.create_message(**kwargs)
        # set board_message_id
        await BoardManager.edit_entry(
            message_id, 
            emoji, 
            None, 
            board_message_id=board_message.id,
        )
    else:
        await bot.rest.edit_message(
            board['channel_id'], 
            board_entry['board_message_id'], 
            embed=embed,
            content=reaction_content,
            attachments=board_entry['attachment_urls']
        )

    

def load(inu: Inu):
    global bot
    bot = inu
    global METHOD_SYNC_TIME
    METHOD_SYNC_TIME = inu.conf.commands.poll_sync_time
    inu.add_plugin(plugin)