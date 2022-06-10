import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari.messages import ButtonStyle
from hikari.impl.special_endpoints import ActionRowBuilder, LinkButtonBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
import lightbulb.utils as lightbulb_utils
from lightbulb import commands, context
from lightbulb import OptionModifier as OM
from lightbulb.context import Context
import hikari
from matplotlib.style import available
from numpy import full, isin
from fuzzywuzzy import fuzz
from pytimeparse.timeparse import timeparse

from utils import Colors, Human, Paginator, crumble, Poll, PollManager
from core import getLogger, Inu

log = getLogger(__name__)

plugin = lightbulb.Plugin("Polls")
bot: Inu

active_polls: List[Poll] = []
letter_emojis =             [
                "🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", 
                "🇭", "", "🇯", "🇰", "🇱", "🇲", "🇳", 
                "🇴", "🇵", "🇶", "🇷", "🇸", "🇹", "🇺", 
                "🇻", "🇼", "🇽", "🇾", "🇿"
            ]
# at start init from database


@plugin.listener(hikari.GuildReactionAddEvent)
async def on_reaction_add(event: hikari.GuildReactionAddEvent):
    log.debug(f"Reaction added: {event.emoji_name=} {event.emoji_id} {str(event.emoji_name)}")
    # change letter_emojis to the actual emoji
    if event.emoji_name not in letter_emojis:
        return
    if not (poll := PollManager.get_poll(event.message_id, event.channel_id)):
        return
    await poll.add_vote_and_update(event.user_id, 1, event.emoji_name)
    

@plugin.command
@lightbulb.command("poll", "start a poll")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def make_poll(ctx: context.SlashContext):
    bot: Inu = plugin.bot
    if isinstance(ctx, context.PrefixContext):
        id = str(bot.id_creator.create_id())
        await ctx.respond(
            component=ActionRowBuilder().add_button(ButtonStyle.PRIMARY, id).set_label("create").add_to_container()
        )
        _, event, interaction = await bot.wait_for_interaction(id)
        ctx_interaction = interaction
    else:
        ctx_interaction = ctx.interaction
    responses, interaction, event = await bot.shortcuts.ask_with_modal(
        modal_title="Creating a poll", 
        question_s=[
            "Poll Headline:", "Poll Description:", "Poll Options:", 
            "Poll Duration:", "Anonymous?"
        ], 
        placeholder_s=[
            "How often do you smoke weed?", 
            "... additional information here if needed ...", 
            "Yes, every day, sometimes, one time, never had and never will be",
            "2 days 5 hours",
            "yes (yes|no|maybe)"
        ],
        interaction=ctx_interaction,
    )
    ctx._interaction = interaction
    ctx._responded = False
    name, description, options, duration, anonymous = responses
    poll = Poll(
        options=options.split(','), 
        active_until=timedelta(seconds=timeparse(duration)),
        anonymous=anonymous.lower() == "yes",
        title=name,
        description=description,
    )
    await poll.start(ctx)

def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)