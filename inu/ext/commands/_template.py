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
    Permissions,
    ButtonStyle
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import Context, Loader, Group, SubGroup, SlashCommand, invoke
from lightbulb.prefab import sliding_window


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

loader = lightbulb.Loader()
bot: Inu

@loader.command
class CommandName(
    SlashCommand,
    name="name",
    description="description",
    dm_enabled=False,
    default_member_permissions=None,
    hooks=[sliding_window(3, 1, "user")]
):
    optional_string = lightbulb.string("message-link", "Delete until this message", default=None)  # Option 1
    optional_int = lightbulb.integer("amount", "The amount of messages you want to delete, Default: 5", default=None) # Option 2
    # when ctx.options.<optional_string> is used, replace it self.<optional_string>

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        ...

