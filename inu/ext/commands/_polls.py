import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging
from datetime import datetime

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

from utils import Colors, Human, Paginator, crumble, Poll, PollManager
from core import getLogger, Inu

log = getLogger(__name__)

plugin = lightbulb.Plugin("Polls")

active_polls: List[Poll] = []
letter_emojis = [f':regional_indicator_{l}:' for l in 'abcdefghijklmnop']
# at start init from database


@plugin.listener(hikari.GuildReactionAddEvent)
async def on_reaction_add(event: hikari.ReactionAddEvent):
    if event.emoji_name not in letter_emojis:
        return
    if not (poll := PollManager.get_poll(event.message_id, event.channel_id)):
        return
    await poll.add_vote_and_update(event.user_id, 1, event.emoji_name)
    


@plugin.listener(lightbulb.events.LightbulbStartedEvent)
async def reinit_open_polls():
    pass

@plugin.command
@lightbulb.command("poll", "start a poll")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def make_poll(ctx: Context):
    bot: Inu = plugin.bot
    responses, interaction, _ = await bot.shortcuts.ask_with_modal(
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
        interaction=ctx.interaction
    )