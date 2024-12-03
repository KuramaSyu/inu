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


from utils import (
    Colors, 
    Human, 
    Paginator, 
    crumble
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

plugin = lightbulb.Plugin("Name", "Description")
bot: Inu

@plugin.command
@lightbulb.command("testmodal", "test command for modal interactions")
@lightbulb.implements(commands.SlashCommand)
async def testmodal(ctx: context.Context):
    bot: Inu = ctx.bot
    answers, interaction, _ = await bot.shortcuts.ask_with_modal(
        "Tag", 
        ["Name:", "Value:"], 
        interaction=ctx.interaction,
        input_style_s=[TextInputStyle.SHORT, TextInputStyle.PARAGRAPH],
        placeholder_s=[None, "What you will see, when you do /tag get <name>"],
        is_required_s=[True, None],
        pre_value_s=[None, "Well idc"]

    )
    await interaction.create_initial_response(ResponseType.MESSAGE_CREATE, f"{answers}")


