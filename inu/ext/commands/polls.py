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
from core import getLogger, Inu, Table
# import Dataset


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
    if event.user_id == bot.me.id:
        return
    if event.emoji_name not in letter_emojis:
        return
    if not event.message_id in PollManager.message_id_cache:
        return

    record = await PollManager.fetch_poll(message_id=event.message_id)
    if not record:
        log.debug(f"no record found")
        return

    option_id = await PollManager.fetch_option_id(
        record["poll_id"], 
        event.emoji_name
    )
    if not option_id:
        log.debug(f"no option_id found for record {record}")
        return
    await PollManager.remove_vote(record["poll_id"], event.user_id)
    await PollManager.add_vote(record["poll_id"], option_id, event.user_id)
    await bot.rest.delete_reaction(event.channel_id, event.message_id, event.user_id, event.emoji_name)


    # check if option in fetched record
    # if yes update poll and insert to votes
    await PollManager.add_vote(
        poll_id=record["poll_id"], 
        user_id=event.user_id, 
        option_id=option_id,
    )
    poll = Poll(record, bot)
    await poll.fetch()
    await poll.dispatch_embed(bot)
    log.debug(f"added vote for {event.user_id} to option {option_id}")


class PollEmbedBuilder:
    def __init__(self, poll_record: Dict[str, str]):
        self._message_id = poll_record["message_id"]
        
    

@plugin.command
@lightbulb.add_checks(lightbulb.guild_only)
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


    message = await (await ctx.respond("Wait...")).message()
    dummy_record = {
        "channel_id": ctx.channel_id,
        "message_id": message.id,
        "creator_id": ctx.author.id,
        "guild_id": ctx.guild_id,
        "title": name,
        "description": description,
        "starts": datetime.now(),
        "expires": datetime.now() + timedelta(seconds=timeparse(duration)),
        "anonymous": anonymous.lower() == "yes",
        "poll_type": 1,
    }
    options = [o.strip() for o in options.split(",") if o.strip()]


    record = await PollManager.add_poll(**dummy_record)
    for letter, option in zip(letter_emojis, options):
        await PollManager.add_poll_option(record["poll_id"], letter, option)
    poll = Poll(record, bot)
    await poll.fetch()
    await poll.dispatch_embed(bot, add_reactions=True)



def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)