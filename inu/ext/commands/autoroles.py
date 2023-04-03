import asyncio
from typing import *
from datetime import datetime
import hikari
import lightbulb

from fuzzywuzzy import fuzz
from hikari import (
    Embed,
    ResponseType, 
    TextInputStyle,
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import commands, context
from tabulate import tabulate


from utils import (
    Colors, 
    Human, 
    Paginator, 
    crumble,
    AutorolesView,
)
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger,
    InuContext,
    get_context
)

log = getLogger(__name__)

plugin = lightbulb.Plugin("Autoroles", "Role Management")
bot: Inu

@plugin.command
@lightbulb.command("autoroles", "a command for editing autoroles")
@lightbulb.implements(commands.SlashCommand)
async def autoroles(ctx: context.Context):
    view = AutorolesView(timeout=10*60)
    await view.pre_start(ctx.guild_id)
    msg = await ctx.respond(components=view, embed=await view.embed())
    await view.start(await msg.message())


def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

