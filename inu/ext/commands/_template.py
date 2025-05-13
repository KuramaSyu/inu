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
    ButtonStyle,
    InteractionCreateEvent,
    ApplicationContextType
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import Context, Loader, Group, SubGroup, SlashCommand, invoke
from lightbulb.prefab import sliding_window
from lightbulb import commands, context
from humanize import precisedelta

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

# in old code lightbulb.Plugin() => remove
loader = lightbulb.Loader()
bot: Inu


@loader.error_handler
async def handler(exc: lightbulb.exceptions.ExecutionPipelineFailedException) -> bool:
    ...

@loader.command
class CommandName(
    SlashCommand,
    name="name",
    description="description",
    contexts=[ApplicationContextType.GUILD],
    default_member_permissions=None,
    hooks=[sliding_window(3, 1, "user")]
):
    optional_string = lightbulb.string("message-link", "Delete until this message", default=None)  # Option 1
    optional_int = lightbulb.integer("amount", "The amount of messages you want to delete, Default: 5", default=None) # Option 2
    # when ctx.options.<optional_string> is used, replace it self.<optional_string>

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        ...

# Groups
# in old code done with SubCommand, Group, SubGroup
group = lightbulb.Group(name="group", description="description")

@group.register
class SubCommandName(
    SlashCommand,
    name="name",
    description="description",
    contexts=[ApplicationContextType.GUILD],
    default_member_permissions=None,
    hooks=[sliding_window(3, 1, "user")]
):
    optional_string = lightbulb.string("message-link", "Delete until this message", default=None)  # Option 1
    optional_int = lightbulb.integer("amount", "The amount of messages you want to delete, Default: 5", default=None) # Option 2
    # when ctx.options.<optional_string> is used, replace it self.<optional_string>

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        ...

loader.command(group)

# in old code load() func => remove

