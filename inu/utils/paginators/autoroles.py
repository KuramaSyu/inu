from typing import *
from datetime import datetime, timedelta
import asyncio
import traceback

from tabulate import tabulate
import hikari
from hikari import ComponentInteraction, ButtonStyle
from hikari.impl import MessageActionRowBuilder
import miru
from pytimeparse.timeparse import timeparse
from humanize import naturaldelta

from . import Paginator, StatelessPaginator
from ..db import AutoroleManager, AutoroleBuilder, AutoroleEvent

from utils import crumble
from core import getLogger, InuContext, BotResponseError, Inu

log = getLogger(__name__)


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
        self.stop()

    async def view_check(self, context: miru.ViewContext) -> bool:
        return context.message.id == self.message.id and context.author.id == self.author_id
    


class EventSelectView(miru.View):
    author_id: int
    event: Type[AutoroleEvent]

    def __init__(self, author_id: int) -> None:
        super().__init__(timeout=15*10, autodefer=True)
        self.author_id = author_id
        self.event_id = 0

    @miru.text_select(
            custom_id="event_select", 
            placeholder="Select an event", 
            options=[miru.SelectOption(event.name, str(event.event_id)) for event in AutoroleManager.id_event_map.values()],
    )
    async def event_select(self, select: miru.TextSelect, ctx: miru.ViewContext):
        self.event = AutoroleManager.id_event_map[int(select.values[0])]
        self.stop()

    async def view_check(self, context: miru.ViewContext) -> bool:
        return context.message.id == self.message.id and context.author.id == self.author_id



class AutorolesView(miru.View):
    table_headers = ["ID", "Role", "Event", "duration"]
    table: List[AutoroleBuilder] = []
    selected_row_index = 0
    author_id: int
    
    def __init__(self, author_id: int) -> None:
        super().__init__(timeout=15*10, autodefer=True)
        self.author_id = author_id

    async def pre_start(self, guild_id: int):
        """Fetches events from the database and wraps them in a table
        
        Parameters
        ----------
        guild_id : int
            The guild ID to fetch events for
        """
        try:
            self.table = await AutoroleManager.wrap_events_in_builder(
                await AutoroleManager.fetch_events(guild_id, None)
            )
        except IndexError:
            self.table = []
        if not self.table:
            builder = AutoroleBuilder()
            builder.guild = guild_id
            self.table = [builder]

    async def start(self, message: hikari.Message):
        await super().start(message)

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
        builder = AutoroleBuilder()
        builder.guild = self._last_context.guild_id
        self.table.insert(self.selected_row_index, builder)
        await self.render_table()

    @miru.button(label="➖", style=ButtonStyle.SECONDARY, custom_id="autoroles_remove")
    async def button_remove(self, button: miru.Button, ctx: miru.ViewContext):
        event = self.table.pop(self.selected_row_index)
        maybe_deleted = await event.delete()
        await self.render_table()
        await ctx.respond(
            f"Event with ID {event.id} was {'' if maybe_deleted else 'not '}deleted.",
            flags=hikari.MessageFlag.EPHEMERAL
        )

    @miru.button(emoji="📌", label="Set Role", style=ButtonStyle.SECONDARY, custom_id="autoroles_set_role", row=2)
    async def button_set_role(self, button: miru.Button, ctx: miru.ViewContext):
        role_select = RoleSelectView(ctx.author.id)
        msg = await ctx.edit_response(components=role_select)
        await role_select.start(await msg.retrieve_message())
        await role_select.wait()
        if not role_select.roles:
            return
        await self.start(await msg.retrieve_message())
        self.table[self.selected_row_index].role = role_select.roles[0]
        await self.render_table()


    @miru.button(emoji="📅", label="Set Event", style=ButtonStyle.SECONDARY, custom_id="autoroles_set_event", row=2)
    async def button_set_event(self, button: miru.Button, ctx: miru.ViewContext):
        event_select = EventSelectView(ctx.author.id)
        msg = await ctx.edit_response(components=event_select)
        await event_select.start(await msg.retrieve_message())
        await event_select.wait()
        if not event_select.event:
            return
        await self.start(await msg.retrieve_message())
        self.table[self.selected_row_index].event = event_select.event
        await self.render_table()


    @miru.button(emoji="🕒", label="Set Duration", style=ButtonStyle.SECONDARY, custom_id="autoroles_set_duration", row=2)
    async def button_set_duration(self, button: miru.Button, ctx: miru.ViewContext):
        bot: Inu = ctx.bot
        answer, interaction, event = None, None, None
        try:
            answer, interaction, event = await bot.shortcuts.ask_with_modal(
                "Duration",
                "Duration:",
                ctx.interaction,
                placeholder_s="2 weeks 5 days"
            )
        except asyncio.TimeoutError:
            return
        if not answer:
            return
        duration = timeparse(answer)
        ctx._interaction = interaction
        if not duration:
            await ctx.respond("Invalid duration. Use something like 3 weeks or 20 days", flags=hikari.MessageFlag.EPHEMERAL)
            return
        self.table[self.selected_row_index].duration = timedelta(seconds=duration)
        await self.render_table()

    # save button
    @miru.button(emoji="💾", label="Save", style=ButtonStyle.SECONDARY, custom_id="autoroles_save", row=2)
    async def button_save(self, button: miru.Button, ctx: miru.ViewContext):
        await ctx.respond("Start..", flags=hikari.MessageFlag.EPHEMERAL)
        await self.save_rows()
        await ctx.edit_response("Saved!", flags=hikari.MessageFlag.EPHEMERAL)
        
    @miru.button(emoji="❌", label="Stop", style=ButtonStyle.SECONDARY, custom_id="autoroles_close")
    async def button_close(self, button: miru.Button, ctx: miru.ViewContext):
        await self.render_table(update_db=False)
        await (await ctx.get_last_response()).delete()
        self.stop()

    async def render_table(self, update_db: bool = True):
        """Renders the table and updates the message."""
        if update_db:
            await self.save_rows()
        if not self.table:
            self.table.append(AutoroleBuilder())
        embed = await self.embed()
        await self._last_context.edit_response(embed=embed, components=self)

    async def embed(self) -> hikari.Embed:
        """Renders the table as an embed."""
        DEFAULT_NONE_VALUE = "---"
        table = []
        for index, row in enumerate(self.table):
            row_marker = "" if index != self.selected_row_index else ">"
            table.append([
                row_marker + str(row.id or DEFAULT_NONE_VALUE),
                str(row.role) or DEFAULT_NONE_VALUE,
                (None if not row.event else row.event.name) or DEFAULT_NONE_VALUE,
                (naturaldelta(row.duration) if row.duration else None) or "∞",
            ])
        rendered_table = tabulate(table, headers=self.table_headers, tablefmt="simple_grid", maxcolwidths=[4, 15, 15, 10])
        return hikari.Embed(
            title="Autoroles",
            description=f"```{rendered_table}```"
        )

    async def save_rows(self):
        """Saves all rows in the table if possible."""
        for row in self.table:
            saved = await row.save()
            log.trace(f"{saved=}; {row=}")

    async def view_check(self, context: miru.ViewContext) -> bool:
        """predicate to check wether or not a user is allowed to use the view."""
        return context.message.id == self.message.id and context.author.id == self.author_id
    
class AutorolesViewer(StatelessPaginator):
    """
    Viewer for which person has got which role
    by a given autorole event
    """
    def __init__(self):
        super().__init__(
            disable_paginator_when_one_site=False
        )
        self._autorole_id = None
        self._with_update_button = True


    @property
    def custom_id_type(self):
        return "autoroles"
    
    def _get_custom_id_kwargs(self):
            """
            Returns a dictionary containing the custom ID keyword arguments for the autorole.

            autoid: int
                The autorole ID to use
            
            Returns:
                dict: A dictionary with the custom ID keyword arguments.
            """
            return {
                "autoid": self._autorole_id
            }
    def set_autorole_id(self, autorole_id: int) -> "AutorolesViewer":
        """
        Set the autorole ID. This should be used in a builder chain 
        before calling `self.start`

        Parameters:
        - autorole_id (int): The ID of the autorole.

        Returns:
        - AutoroleView: The updated AutoroleView instance.
        """
        self._autorole_id = autorole_id
        return self
    
    async def start(self, ctx: InuContext):
        self.set_context(ctx)
        await self._set_pages_with_autorole_id(self._autorole_id)
        await super().start(ctx)

    async def _rebuild(self, event: hikari.ComponentInteraction):
        self.set_context(event=event)
        self._autorole_id = self.custom_id.get("autoid")
        autorole_event = AutoroleManager.id_event_map.get(self._autorole_id)
        await self._set_pages_with_autorole_id(autorole_event)

    async def _set_pages_with_autorole_id(self, autorole_id: int):
        autorole_event = AutoroleManager.id_event_map.get(self._autorole_id)
        if not autorole_event:
            self.set_pages(["Autorole event does not exist any longer."])
            return
        records = await AutoroleManager.fetch_instances(self.ctx.guild_id, event=autorole_event)
        self.set_pages(self.make_autorole_strings(records, self.ctx.guild_id))
        

    def make_autorole_strings(
        self,
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
        records.sort(key=lambda x: x["expires_at"])
        for i, record in enumerate(records):
            try:
                table["ID"].append(str(record["id"]))
            except Exception:
                table["ID"].append("?")

            try:
                table["Role"].append(self.ctx.bot.cache.get_role(record["role_id"]).name)
            except Exception:
                table["Role"].append("?")

            try:
                table["Member"].append(self.ctx.bot.cache.get_member(guild_id, record["user_id"]).display_name)
            except Exception:
                table["Member"].append("?")

            try:
                table["Expires in"].append(naturaldelta(value=record["expires_at"] - datetime.utcnow()))
            except Exception:
                traceback.print_exc()
                table["Expires in"].append("?")
        
        string = tabulate(table, headers=table.keys(), tablefmt="simple_grid")
        return [f"```\n{x}\n```" for x in crumble(string, 2000, seperator="\n")]