import random
from fractions import Fraction
import os
import traceback
import typing
from typing import Union
import logging
from async_timeout import asyncio

import hikari
import lightbulb
from lightbulb.context import Context
from lightbulb import Bucket, commands
from lightbulb import errors
from lightbulb import events
from lightbulb.commands import OptionModifier as OM

from utils.games.connect_four_handler import Connect4Handler

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

plugin = lightbulb.Plugin("Game Commands", "Extends the commands with commands all about games")

@plugin.command
@lightbulb.option("player2", "The second player - DEFAULT: you", type=hikari.Member, default=None)
@lightbulb.option("player1", "A player\nNOTE: ping like @user", type=hikari.Member)
@lightbulb.command("connect4", "starts a Connect 4 game", aliases=["con4", "connect-4"])
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def connect4(ctx: Context):
    h = Connect4Handler(ctx.options.player1, ctx.options.player2 or ctx.member)
    msg = await h.start(ctx)
    log.debug(msg)
    await msg.add_reaction("🔁")
    try:
        await plugin.bot.wait_for(
            hikari.ReactionAddEvent,
            timeout=15*60,
            predicate=lambda e: (
                    e.message_id == msg.id
                    and e.user_id in [ctx.options.player1.id, ctx.options.player2.id]
                    and e.emoji_name == "🔁"
            )
        )
        await connect4.callback(ctx)
    except asyncio.TimeoutError:
        pass
    await msg.remove_all_reactions()
    
    
def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)