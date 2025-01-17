import asyncio
import logging
import typing
from datetime import datetime
from typing import *
from numpy import full, isin

import aiohttp
import hikari
import lightbulb
import lightbulb.utils as lightbulb_utils

from fuzzywuzzy import fuzz
from hikari import (
    ActionRowComponent, 
    Embed, 
    MessageCreateEvent, 
    embeds, 
    ResponseType, 
    TextInputStyle,
    Permissions,
    ButtonStyle
)
from hikari.events import InteractionCreateEvent
from hikari.impl.special_endpoints import MessageActionRowBuilder, LinkButtonBuilder
from hikari.impl import MessageActionRowBuilder
from lightbulb import commands, context, Loader, Group, SubGroup, SlashCommand, invoke
from lightbulb.context import Context
from lightbulb.prefab import sliding_window
from matplotlib.style import available
from typing_extensions import Self


from utils import (
    Colors, 
    Human, 
    Paginator, 
    Reddit, 
    Urban, 
    crumble,
    Watch2Gether
)
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger,
    InuContext
)

log = getLogger(__name__)
loader = lightbulb.Loader()
bot: Inu

@loader.command
class Watch2GetherCommand(
    SlashCommand,
    name="watch2gether",
    description="Create a W2G room",
    dm_enabled=False,
    default_member_permissions=None,
    hooks=[sliding_window(3, 1, "user")]
):
    optional_link = lightbulb.string("link", "An optional YouTube video to add", default=None)  # Option 1

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        resp = await Watch2Gether.fetch_link(self.optional_link)
        await ctx.respond(
            component=(
                MessageActionRowBuilder()
                .add_link_button(
                    resp['room-link'],
                    label="Watch2Gether Room"
                )
            )
        )


