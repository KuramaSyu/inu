import typing
from typing import (
    Union,
    Optional,
    List,
    Dict
)
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari import ButtonStyle, ApplicationContextType
from hikari.impl.special_endpoints import MessageActionRowBuilder, LinkButtonBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
import lightbulb.utils as lightbulb_utils
from lightbulb import commands, context, SlashCommand, invoke, Loader
from lightbulb.context import Context
import hikari
from matplotlib.style import available
from numpy import full, isin
from fuzzywuzzy import fuzz
from pytimeparse.timeparse import timeparse
from hikari import TextInputStyle

from utils import Colors, Human, Paginator, crumble, Poll, PollManager
from core import getLogger, Inu, Table, BotResponseError, ComponentContext, InuContext, get_context
# import Dataset


log = getLogger(__name__)

loader = lightbulb.Loader()
bot: Inu = Inu.instance
POLL_SYNC_TIME: int = 0

# Global variables moved to top
active_polls: List[Poll] = []
letter_emojis = [
    "🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", 
    "🇭", "", "🇯", "🇰", "🇱", "🇲", "🇳", 
    "🇴", "🇵", "🇶", "🇷", "🇸", "🇹", "🇺", 
    "🇻", "🇼", "🇽", "🇾", "🇿"
]

@loader.listener(hikari.InteractionCreateEvent)
async def on_interaction_create(event: hikari.InteractionCreateEvent):
    """handler for poll interactions"""
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    ictx = get_context(event)
    log = getLogger(__name__, "INTERACTION RECEIVE")
    
    if ictx.user.id == bot.me.id:
        return
    if not (custom_id := ictx.custom_id).startswith("vote_add"):
        return
    letter = custom_id[-1]
    ctx_message_id = (await ictx.message()).id
    if not ctx_message_id in PollManager.message_id_cache:
        log.debug("message id not in cache")
        return

    record = await PollManager.fetch_poll(message_id=ctx_message_id)
    if not record:
        log.debug("no poll record found")
        return

    option_id = await PollManager.fetch_option_id(
        record["poll_id"], 
        letter
    )
    if not option_id:
        log.debug("no option id found")
        return
    
    await PollManager.remove_vote(record["poll_id"], ictx.author.id)
    # check if option in fetched record
    # if yes update poll and insert to votes
    await PollManager.add_vote(
        poll_id=record["poll_id"], 
        user_id=ictx.author.id, 
        option_id=option_id,
    )
    # create poll object
    poll = Poll(record, bot)
    # update all poll values to the current status
    await poll.fetch()
    # dispatch the message
    await poll.dispatch_embed(ictx)



@loader.listener(hikari.MessageDeleteEvent)
async def on_message_delete(event: hikari.MessageDeleteEvent):
    """delete poll from db"""
    if not event.message_id in PollManager.message_id_cache:
        return
    log = getLogger(__name__, "ON MESSAGE DELETE")
    log.debug(f"remove message with id {event.message_id}")
    await PollManager.remove_poll(event.message_id)
        

@loader.command
class PollCommand(
    SlashCommand,
    name="poll",
    description="start a poll",
    contexts=[ApplicationContextType.GUILD]
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        bot: Inu = ctx.bot
        try:
            responses, new_ctx = await ctx.ask_with_modal(
                title="Creating a poll", 
                question_s=[
                    "Poll Headline:", "Additional information:", "Poll Options:", 
                    "Poll Duration:", "Anonymous?"
                ], 
                placeholder_s=[
                    "How often do you smoke weed?", 
                    "... additional information here if needed ...", 
                    "Yes, every day, sometimes, one time, never had and never will be",
                    "3 hours 30 minutes",
                    "yes [yes|no]"
                ],
                is_required_s=[True, False, True, True, True],
                input_style_s=[
                    TextInputStyle.SHORT, 
                    TextInputStyle.PARAGRAPH,
                    TextInputStyle.PARAGRAPH,
                    TextInputStyle.SHORT,
                    TextInputStyle.SHORT
                ],
                max_length_s=[255, 2048, None, None, None],
            )
            if new_ctx is None:
                return
            ctx = new_ctx
        except asyncio.TimeoutError:
            return

        name, description, options, duration, anonymous = responses
        
        try:
            dummy_record = {
                "channel_id": ctx.channel_id,
                "message_id": None,
                "creator_id": ctx.author.id,
                "guild_id": ctx.guild_id,
                "title": name,
                "description": description,
                "starts": datetime.now(),
                "expires": datetime.now() + timedelta(seconds=timeparse(duration)),
                "anonymous": anonymous.lower() == "yes",
                "poll_type": 1,
                "show_scale": False,
                "amount_of_choices": -1,
            }
        except Exception:
            raise BotResponseError(
                (
                    "Your given time is not valid.\n"
                    "Maybe you forgot the type? (e.g. hours, minutes, seconds..)\n"
                    f"You have given me this: `{duration}`"
                ),
                
                ephemeral=True,
            )

        options = [o.strip() for o in options.split(",") if o.strip()]
        if len(options) <= 1:
            if not "," in options[0]:
                hint = "**HINT:** Seperate your options with `,` like `kiwi, mango, green apple, blue bananna`" 
            else:
                hint = ""
            raise BotResponseError(
                bot_message=(
                    f"You need to enter at least two options.\n"
                    f"You have entered {Human.plural_('option', len(options), with_number=True)}.\n"
                    f"{hint}"
                ),
                ephemeral=True,
            )
        if len(options) > 15:
            raise BotResponseError(
                f"You enter a maximum of 15 options.\nYou have entered {Human.plural_('option', len(options), with_number=True)}.",
                ephemeral=True,
            )
        for option in options:
            if len(option) > 80:
                raise BotResponseError((
                    f"Your option `{option}` is longer than 80 characters. Make sure, it's 80 or below"
                ))
        if dummy_record["expires"] <= datetime.now() + timedelta(seconds=9):  # type: ignore
            raise BotResponseError(
                f"You need to enter a duration that is longer than 9 seconds",
                ephemeral=True,
            )
        if dummy_record["expires"] >= datetime.now() + timedelta(days=90):  # type: ignore
            raise BotResponseError(
                f"You need to enter a duration that is shorter than 90 days",
                ephemeral=True,
            )

        message = await (await ctx.respond("Wait...")).message()
        dummy_record["message_id"] = message.id

        record = await PollManager.add_poll(**dummy_record)
        for letter, option in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", options):
            await PollManager.add_poll_option(
                poll_id=record["poll_id"], 
                reaction=letter, 
                description=option
            )
        poll = Poll(record, bot)
        await poll.fetch()
        await poll.dispatch_embed(ctx, content="")
        if poll.expires < datetime.now() + timedelta(seconds=POLL_SYNC_TIME):
            await poll.finalize()

# Initialize POLL_SYNC_TIME
@loader.listener(hikari.StartedEvent)
async def on_ready(_: hikari.StartedEvent):
    global POLL_SYNC_TIME
    POLL_SYNC_TIME = bot.conf.commands.poll_sync_time