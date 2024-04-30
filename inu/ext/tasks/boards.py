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
from utils import make_message_link, Colors, Multiple, Human

log = getLogger(__name__)
BOARD_SYNC_TIME = 60*60*24
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
    await clean_boards()

    trigger = IntervalTrigger(seconds=BOARD_SYNC_TIME)
    log.info(f"scheduled job for boards update: {trigger}", prefix="init")
    plugin.bot.scheduler.add_job(clean_boards, trigger)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    await init_method()

async def init_method():
    pass

async def clean_boards():
    max_age = datetime.now() - timedelta(days=bot.conf.commands.board_entry_lifetime)
    table = Table("board.entries")
    records = await table.execute(
        (
            f"DELETE FROM {table.name}\n"
            f"WHERE created_at < $1"
        ), max_age
    )
    if records:
        log.info(f"deleted {Human.plural_('board-entry', len(records), with_number=True)}", prefix="task")

@plugin.listener(hikari.GuildReactionAddEvent)
async def on_reaction_add(event: hikari.GuildReactionAddEvent):
    log.debug(f"REACTION ADD receiving: {event.emoji_name}")
    # insert to board

    # guild has no board with this reaction
    if not BoardManager.has_emoji(event.guild_id, event.emoji_name):
        log.debug(f"emoji not tracked")
        return
    
    message: Optional[hikari.Message] = None
    entry = await BoardManager.fetch_entry(event.message_id, event.emoji_name)
    if not entry:
        log.debug(f"no entry found => add entry")
        message = await bot.rest.fetch_message(event.channel_id, event.message_id)
        if not message:
            log.debug(f"reaction message not found")
            return
        attachment_urls = [str(a.url) for a in message.attachments]
        content = message.content or ""
        # add first embed to content
        if len(message.embeds) > 0:
            if message.embeds[0].title:
                content += f"\n**{message.embeds[0].title}**"
            if message.embeds[0].description:
                content += f"\n{message.embeds[0].description}"
            if message.embeds[0].image:
                attachment_urls.append(str(message.embeds[0].image.url))
        # put picture things in front. Otherwise Python bug
        attachment_urls.sort(key=lambda a: Multiple.endswith_(a, [".jpg", ".png", ".webp"]), reverse=True)
        if not message:
            log.debug("message not found")
            return
        # add entry
        entry = (await BoardManager.add_entry(
            guild_id=event.guild_id,
            message_id=event.message_id,
            author_id=message.author.id or event.user_id,
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
    try:
        await update_message(entry, message, optional_author_id=event.user_id)
    except hikari.NotFoundError as e:
        if not e.code == 10003:
            # not a unknown channel
            return
        log.info(f"[Deleted] {event.emoji_name}-baord in guild {event.guild_id} because of unknown channel")
        await BoardManager.remove_board(event.guild_id, event.emoji_name)




    # method for updating a message in a board

@plugin.listener(hikari.GuildReactionDeleteEvent)
async def on_reaction_remove(event: hikari.GuildReactionDeleteEvent):
    log = getLogger(__name__, "REACTION REMOVE")
    # delete from board
    emoji = event.emoji_name
    log.debug(f"receiving: {emoji}")

    # guild has no board with this reaction
    if not BoardManager.has_emoji(event.guild_id, event.emoji_name):
        log.debug(f"emoji not tracked")
        return

    # board don't has this message -> create entry
    if not BoardManager.has_message_id(event.guild_id, event.emoji_name, event.message_id):
        log.debug(f"message not tracked")
        return
    try:
        removed_records = await BoardManager.remove_reaction(
            guild_id=event.guild_id,
            message_id=event.message_id,
            reacter_id=event.user_id,
            emoji=event.emoji_name,
        )
    except Exception:
        log.warning(f"insertion error, which shouldn't occure.\n{traceback.format_exc()}")
    # TODO: when a message has no reactions any more, delete it 
    # (db will be cleared automatically -> when updating message results in error, delete message)
    if not removed_records:
        return
    
    if (amount := await BoardManager.fetch_entry_reaction_amount(event.message_id, emoji)) == 0:
        # delete board entry
        log.debug(f"entry has {amount} reactions -> removing it")
        entry = await BoardManager.remove_entry(event.message_id, emoji)
        if not entry:
            log.debug(f"No entry was deleted ")
            return
        board = await BoardManager.fetch_board(event.guild_id, emoji)
        await bot.rest.delete_message(board["channel_id"], entry[0]["board_message_id"])
        log.debug(f"message {entry[0]['board_message_id']} deleted")
    else:
        entry = await BoardManager.fetch_entry(event.message_id, emoji)
        await update_message(entry, reaction_amount=amount, optional_author_id=event.user_id)



@plugin.listener(hikari.GuildMessageDeleteEvent)
async def on_message_remove(event: hikari.GuildMessageDeleteEvent):
    if not BoardManager.has_message_id(event.guild_id, None, event.message_id):
        return
    await BoardManager.remove_entry(event.message_id, None)


@plugin.listener(hikari.GuildLeaveEvent)
async def on_guild_leave(event: hikari.GuildLeaveEvent):
    # remove all boards
    getLogger(__name__, "GUILD LEAVE")
    board_records = await BoardManager.remove_board(event.guild_id)
    log.debug(f"removed {len(board_records)} boards from {event.guild_id}")


async def update_message(
    board_entry: Dict[str, Any],
    message: Optional[hikari.Message] = None,
    reaction_amount: int | None = None,
    optional_author_id: int | None = None,
):
    channel_id = board_entry["channel_id"]
    message_id = board_entry["message_id"]
    guild_id = board_entry["guild_id"]
    content = board_entry["content"]
    emoji = board_entry["emoji"]

    # fetch author or event author
    try:
        author = await bot.mrest.fetch_member(guild_id, board_entry["author_id"])
    except Exception as e:
        if not optional_author_id:
            log.error(traceback.format_exc())
            return
        author = await bot.mrest.fetch_member(guild_id, optional_author_id)
        await BoardManager.edit_entry(
            message_id=message_id,
            emoji=emoji,
            author_id=optional_author_id,
        )
    if not author:
        log.warning(f"no member with id {board_entry['author_id']} found")
        return

    message_votes = reaction_amount or await BoardManager.fetch_entry_reaction_amount(message_id, emoji)
    board = await BoardManager.fetch_board(guild_id, emoji)


    color_stages = {
        n: color for n, color in zip(
            range(1,100),
            [
                "royalblue", "slateblue",
                "mediumpurple", "blueviolet", "indigo",
                "mediumorchid", "purple", "darkmagenta", "mediumvioletred",
                "deeppink", "crimson"
            ]
        )
    }
    color = color_stages.get(message_votes, "crimson")
    reaction_content = f"{message_votes}x {emoji}"
    embeds: List[Embed] = []
    embed = Embed()
    embed.set_author(
        name=f"{author.username}", 
        icon=author.display_avatar_url
    )

    embed.description = (
        f"Jump to the message: "
        f"{make_message_link(guild_id, channel_id, message_id)}\n{content}"
    )
    # embed color -> how many stars
    embed.color = Colors.from_name(color)
    embeds.append(embed)

    # move attachment pics into embeds
    if (attachments:=board_entry['attachment_urls']):
        to_remove: List[str] = []
        for attachment in board_entry['attachment_urls']:
            if Multiple.endswith_(attachment, [".jpg", ".png", ".webp"]):
                if len(to_remove) == 0:
                    embeds[0].set_image(attachments[0])
                    to_remove.append(attachment)
                    continue
                embed = Embed()
                embed.set_image(attachment)
                embed.color = Colors.from_name(color)
                embeds.append(embed)
                to_remove.append(attachment)
        for r_attachment in to_remove:
            board_entry['attachment_urls'].remove(r_attachment)

    if not board_entry["board_message_id"]:
        # create new message and add message_id to entry
        if not message:
            raise RuntimeError(
                "in update_message:\nif board entry gets created first time, a message musst be passed in"
            )

        kwargs = {
            "attachments": board_entry['attachment_urls'],
            "embeds": embeds,
            "content": reaction_content,
            # "components": message.components,
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
            embeds=embeds,
            content=reaction_content,
        )

    

def load(inu: Inu):
    global bot
    bot = inu
    global BOARD_SYNC_TIME
    BOARD_SYNC_TIME = inu.conf.commands.board_sync_time * 60 * 60
    inu.add_plugin(plugin)