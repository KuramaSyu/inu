import asyncio
from typing import *
from datetime import datetime
import hikari
import lightbulb
import traceback

from fuzzywuzzy import fuzz
from humanize import naturaldelta
from hikari import (
    Embed,
    ResponseType, 
    TextInputStyle,
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import commands, context
from tabulate import tabulate
from utils.db import AutoroleEvent


from utils import (
    Colors, 
    Human, 
    Paginator, 
    crumble,
    AutorolesView,
    AutoroleManager,
    AutorolesViewer,
    CustomID
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
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.app_command_permissions(hikari.Permissions.MANAGE_ROLES)
@lightbulb.command("autoroles", "a command for editing autoroles")
@lightbulb.implements(commands.SlashCommandGroup)
async def autoroles(ctx: context.Context):
    ...

@autoroles.child()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.app_command_permissions(hikari.Permissions.MANAGE_ROLES)
@lightbulb.command("edit", "a command for editing autoroles")
@lightbulb.implements(commands.SlashSubCommand)
async def autoroles_edit(ctx: context.Context):
    view = AutorolesView(author_id=ctx.author.id)
    await view.pre_start(ctx.guild_id)
    msg = await ctx.respond(components=view, embed=await view.embed())
    await view.start(await msg.message())
    
@autoroles.child()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option(
    "role", 
    "the role to add or remove from the autoroles",
    choices=[v.__name__ for v in AutoroleManager.id_event_map.values()]
)
@lightbulb.command("view", "a command for viewing the autoroles given to members")
@lightbulb.implements(commands.SlashSubCommand)
async def autoroles_view(ctx: context.Context):
    event_id = None
    for k, v in AutoroleManager.id_event_map.items():
        if ctx.options["role"] == v.__name__:
            event_id = k
            break
    pag = AutorolesViewer().set_autorole_id(event_id)
    await pag.start(get_context(ctx.event))
    # records = await AutoroleManager.fetch_instances(ctx.guild_id, event=event)
    # pag = Paginator(page_s=make_autorole_strings(records, ctx.guild_id))
    # await pag.start(ctx)
@plugin.listener(hikari.InteractionCreateEvent)
async def on_autoroles_view_interaction(event: hikari.InteractionCreateEvent):
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    custom_id = CustomID.from_custom_id(event.interaction.custom_id)
    try:
        if not custom_id.type == "autoroles":
            return
    except Exception:
        return
    pag = AutorolesViewer().set_autorole_id(custom_id.get("autoid")).set_custom_id(event.interaction.custom_id)
    await pag.rebuild(event)
    
def make_autorole_strings(
    records: List[Dict[Literal['id', 'user_id', 'expires_at', 'event_id', 'role_id'], Any]],
    guild_id: int
) -> List[str]:
    AMOUNT_PER_PAGE = 15
    def bare_table() -> Dict:
        return {
            "ID": [],
            "Role": [],
            "Member": [],
            "Expires in": []
        }
    table = bare_table()
    
    for i, record in enumerate(records):
        try:
            table["ID"].append(str(record["id"]))
        except Exception:
            table["ID"].append("?")

        try:
            table["Role"].append(bot.cache.get_role(record["role_id"]).name)
        except Exception:
            table["Role"].append("?")

        try:
            table["Member"].append(bot.cache.get_member(guild_id, record["user_id"]).display_name)
        except Exception:
            table["Member"].append("?")

        try:
            table["Expires in"].append(naturaldelta(value=record["expires_at"] - datetime.utcnow()))
        except Exception:
            traceback.print_exc()
            table["Expires in"].append("?")
    
    string = tabulate(table, headers=table.keys(), tablefmt="simple_grid")
    return [f"```\n{x}\n```" for x in crumble(string, 2000, seperator="\n")]
                
        
    
    

def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

