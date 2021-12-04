import random
from fractions import Fraction
import os
import traceback
import typing
from typing import Union
import logging

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
@lightbulb.option("player2", "The second player", type=hikari.Member, default=None)
@lightbulb.option("player1", "The first player. Default: you\nNOTE: ping the player like @user", type=hikari.Member, default=None)
@lightbulb.command("connect4", "starts a Connect 4 game", aliases=["con4", "connect-4"])
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def connect4(ctx: Context):
    h = Connect4Handler(ctx.options.player1 or ctx.member, ctx.options.player2)
    await h.start(ctx)
    
    
def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)