from typing import *
from datetime import datetime
import hikari
import lightbulb
import traceback

from humanize import naturaldelta
import hikari
from lightbulb import commands, context, SlashCommand, invoke, Loader
from tabulate import tabulate


from utils import (
    crumble,
    AutorolesScreen,
    AutoroleManager,
    AutorolesViewer,
    CustomID
)
from core import (
    Inu, 
    getLogger,
    get_context,
    InuContext
)
import miru 
from miru.ext.menu import menu

log = getLogger(__name__)

loader = lightbulb.Loader()
bot: Inu = Inu.instance
client = bot.miru_client

autoroles_group = lightbulb.Group(
    name="autoroles",
    description="Role Management",
    dm_enabled=False,
    default_member_permissions=hikari.Permissions.MANAGE_ROLES
)

@autoroles_group.register
class AutorolesEdit(
    SlashCommand,
    name="edit",
    description="a command for editing autoroles",
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        menu = miru.ext.menu.Menu()
        screen = AutorolesScreen(menu, ctx.author_id)
        await screen.pre_start(ctx.guild_id)
        builder = await menu.build_response_async(client, screen)
        await builder.create_initial_response(ctx.interaction)
        client.start_view(menu)


@autoroles_group.register
class AutorolesViewCommand(
    SlashCommand,
    name="view",
    description="a command for viewing the autoroles given to members",
):
    role = lightbulb.string(
        "role",
        "the role to add or remove from the autoroles",
        choices=[lightbulb.Choice(v.__name__, v.__name__) for v in AutoroleManager.id_event_map.values()]
    )

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        event_id = None
        for k, v in AutoroleManager.id_event_map.items():
            if self.role == v.__name__:
                event_id = k
                break
        pag = AutorolesViewer().set_autorole_id(event_id)
        await pag.start(ctx)

@loader.listener(hikari.InteractionCreateEvent)
async def on_autoroles_view_interaction(event: hikari.InteractionCreateEvent):
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    custom_id = CustomID.from_custom_id(event.interaction.custom_id)
    try:
        if not custom_id.type == "autoroles":
            return
    except Exception:
        return
    log.debug(f"custom_id: {custom_id}")
    pag = AutorolesViewer().set_autorole_id(custom_id.get("autoid")).set_custom_id(event.interaction.custom_id)
    await pag.rebuild(event.interaction)

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

loader.command(autoroles_group)

