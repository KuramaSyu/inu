from typing import *

from tabulate import tabulate
import hikari
from hikari import ComponentInteraction, ButtonStyle
from hikari.impl import MessageActionRowBuilder
import miru

from . import Paginator
from ..db import AutoroleManager, AutoroleBuilder


class AutorolesPaginator(Paginator):
    table_headers = ["ID", "Role", "Event", "duration"]
    table: List[AutoroleBuilder] = []
    selected_row_index = 0

    def build_default_components(self, position=None) -> List[MessageActionRowBuilder]:
        rows = []
        rows.append(
            MessageActionRowBuilder()
            .add_button(ButtonStyle.SECONDARY, "autoroles_up").set_label("⬆️").add_to_container()
            .add_button(ButtonStyle.SECONDARY, "autoroles_down").set_label("⬇️").add_to_container()
            .add_button(ButtonStyle.SECONDARY, "autoroles_add").set_label("➕").add_to_container()
            .add_button(ButtonStyle.SECONDARY, "autoroles_remove").set_label("➖").add_to_container()
        )
        rows.append(
            MessageActionRowBuilder()
            .add_button(ButtonStyle.SECONDARY, "autoroles_set_role").set_label("📌 Set Role").add_to_container()
            .add_button(ButtonStyle.SECONDARY, "autoroles_set_event").set_label("📅 Set Event").add_to_container()
            .add_button(ButtonStyle.SECONDARY, "autoroles_set_duration").set_label("🕒 Set Duration").add_to_container()
        )
        return rows

    async def render(self):
        ...

    async def _update_position(self, interaction: ComponentInteraction | None = None,):
        """
        replaces embed page first with a more detailed one, before sending the message
        """
        await self.render()
        await super()._update_position(interaction)

class RoleSelectView(miru.View):
    author_id: int
    roles: Sequence[hikari.Role] = []

    def __init__(self, author_id: int) -> None:
        super().__init__(timeout=15*10, autodefer=True)
        self.author_id = author_id
        self.roles = []

    @miru.role_select(custom_id="role_select", placeholder="Select a role")
    async def role_select(self, select: miru.RoleSelect, ctx: miru.ViewContext):
        self.roles = select.values

    async def view_check(self, context: miru.ViewContext) -> bool:
        return context.message.id == self.message.id and context.author.id == self.author_id

class AutorolesView(miru.View):
    table_headers = ["", "ID", "Role", "Event", "duration"]
    table: List[AutoroleBuilder] = []
    selected_row_index = 0

    @miru.button(label="⬆️", style=ButtonStyle.SECONDARY, custom_id="autoroles_up")
    async def button_up(self, button: miru.Button, ctx: miru.ViewContext):
        self.selected_row_index = max(0, self.selected_row_index - 1)
        await self.render_table()
    
    @miru.button(label="⬇️", style=ButtonStyle.SECONDARY, custom_id="autoroles_down")
    async def button_down(self, button: miru.Button, ctx: miru.ViewContext):
        self.selected_row_index = min(len(self.table) - 1, self.selected_row_index + 1)
        await self.render_table()

    @miru.button(label="➕", style=ButtonStyle.SECONDARY, custom_id="autoroles_add")
    async def button_add(self, button: miru.Button, ctx: miru.ViewContext):
        self.table.insert(self.selected_row_index, AutoroleBuilder())
        await self.render_table()

    @miru.button(label="➖", style=ButtonStyle.SECONDARY, custom_id="autoroles_remove")
    async def button_remove(self, button: miru.Button, ctx: miru.ViewContext):
        self.table.pop(self.selected_row_index)
        await self.render_table()

    @miru.button(emoji="📌", label="Set Role", style=ButtonStyle.SECONDARY, custom_id="autoroles_set_role")
    async def button_set_role(self, button: miru.Button, ctx: miru.ViewContext):
        role_select = RoleSelectView(ctx.author.id)
        msg = await ctx.respond(components=role_select)
        await role_select.start(await msg.retrieve_message())
        await role_select.wait()
        if not role_select.roles:
            return
        self.table[self.selected_row_index].role_id = role_select.roles[0].id




    async def render_table(self):
        DEFAULT_NONE_VALUE = "---"
        table = []
        for index, row in enumerate(self.table):
            row_marker = " " if index != self.selected_row_index else ">"
            table.append([
                row_marker,
                row.id or DEFAULT_NONE_VALUE,
                row.role_id or DEFAULT_NONE_VALUE,
                row.event or DEFAULT_NONE_VALUE,
                row.duration or DEFAULT_NONE_VALUE,
            ])
        rendered_table = tabulate(table, headers=self.table_headers, tablefmt="rounded_outline")
        embed = hikari.Embed(
            title="Autoroles",
            description=f"```{rendered_table}```"
        )
        await self.last_context.respond(embed=embed) 