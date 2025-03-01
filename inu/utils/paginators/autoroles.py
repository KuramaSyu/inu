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
from miru.ext import menu
from . import Paginator, StatelessPaginator
from ..db import AutoroleManager, AutoroleBuilder, AutoroleEvent

from utils import crumble
from core import getLogger, InuContext, BotResponseError, Inu, get_context

client = Inu()._miru
log = getLogger(__name__)



class RoleSelectScreen(menu.Screen):
    def __init__(self, menu_instance: menu.Menu, author_id: int) -> None:
        super().__init__(menu_instance)
        self.author_id = author_id
        self.roles = []

    async def build_content(self) -> menu.ScreenContent:
        return menu.ScreenContent()

    @menu.role_select(custom_id="role_select", placeholder="Select a role")
    async def role_select(self, ctx: miru.ViewContext, select: miru.RoleSelect):
        self.roles = select.values
        await self.menu.pop()
        
class MyModal(miru.Modal, title="Example Title"):

    name = miru.TextInput(
        label="Name",
        placeholder="Type your name!",
        required=True
    )

    bio = miru.TextInput(
        label="Biography",
        value="Pre-filled content!",
        style=hikari.TextInputStyle.PARAGRAPH
    )

    # The callback function is called after the user hits 'Submit'
    async def callback(self, ctx: miru.ModalContext) -> None:
        # You can also access the values using ctx.values,
        # Modal.values, or use ctx.get_value_by_id()
        await ctx.respond(
            f"Your name: `{self.name.value}`\nYour bio: ```{self.bio.value}```"
        )

class EventSelectScreen(menu.Screen):
    def __init__(self, menu_instance: menu.Menu, author_id: int) -> None:
        super().__init__(menu_instance)
        self.author_id = author_id
        self.event = None

    async def build_content(self) -> menu.ScreenContent:
        return menu.ScreenContent()

    @menu.text_select(
        custom_id="event_select", 
        placeholder="Select an event", 
        options=[miru.SelectOption(str(event.name), str(event.event_id)) for event in AutoroleManager.id_event_map.values()],
    )
    async def event_select(self, ctx: miru.ViewContext, select: miru.TextSelect):
        self.event = AutoroleManager.id_event_map[int(select.values[0])]
        await self.menu.pop()

class AutorolesScreen(menu.Screen):
    table_headers = ["ID", "Role", "Event", "duration"]
    
    def __init__(self, menu_instance: menu.Menu, author_id: int) -> None:
        super().__init__(menu_instance)
        self.author_id = author_id
        self.table: List[AutoroleBuilder] = []
        self.selected_row_index = 0

    async def pre_start(self, guild_id: int):
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

    async def build_content(self) -> menu.ScreenContent:
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
        return menu.ScreenContent(
            embed=hikari.Embed(
                title="Autoroles",
                description=f"```{rendered_table}```"
            )
        )

    @menu.button(label="⬆️", style=ButtonStyle.SECONDARY)
    async def button_up(self, ctx: miru.ViewContext, button: menu.ScreenButton):
        self.selected_row_index = max(0, self.selected_row_index - 1)
        await self.menu.update_message()
    
    @menu.button(label="⬇️", style=ButtonStyle.SECONDARY)
    async def button_down(self, ctx: miru.ViewContext, button: menu.ScreenButton):
        self.selected_row_index = min(len(self.table) - 1, self.selected_row_index + 1)
        await self.menu.update_message()

    @menu.button(label="➕", style=ButtonStyle.SECONDARY)
    async def button_add(self, ctx: miru.ViewContext, button: menu.ScreenButton):
        builder = AutoroleBuilder()
        builder.guild = ctx.guild_id
        self.table.insert(self.selected_row_index, builder)
        await self.menu.update_message()

    @menu.button(label="➖", style=ButtonStyle.SECONDARY)
    async def button_remove(self, ctx: miru.ViewContext, button: menu.ScreenButton):
        event = self.table.pop(self.selected_row_index)
        maybe_deleted = await event.delete()
        await self.menu.update_message()
        await ctx.respond(
            f"Event with ID {event.id} was {'' if maybe_deleted else 'not '}deleted.",
            flags=hikari.MessageFlag.EPHEMERAL
        )

    @menu.button(emoji="📌", label="Set Role", style=ButtonStyle.SECONDARY, row=2)
    async def button_set_role(self, ctx: miru.ViewContext, button: menu.ScreenButton):
        role_screen = RoleSelectScreen(self.menu, ctx.author.id)
        await self.menu.push(role_screen)
        if role_screen.roles:
            self.table[self.selected_row_index].role = role_screen.roles[0]
            await self.menu.update_message()

    @menu.button(emoji="📅", label="Set Event", style=ButtonStyle.SECONDARY, row=2)
    async def button_set_event(self, ctx: miru.ViewContext, button: menu.ScreenButton):
        event_screen = EventSelectScreen(self.menu, ctx.author.id)
        await self.menu.push(event_screen)
        if event_screen.event:
            self.table[self.selected_row_index].event = event_screen.event
            await self.menu.update_message()

    @menu.button(emoji="🕒", label="Set Duration", style=ButtonStyle.SECONDARY, custom_id="autoroles_set_duration", row=2)
    async def button_set_duration(self, ctx: miru.ViewContext, button: menu.ScreenButton):
        ictx = get_context(ctx.interaction)
        answer, new_ictx = await ictx.ask_with_modal(
            "Duration",
            "Duration:",
            placeholder_s="2 weeks 5 days"
        )
        if not answer:
            return
        duration = timeparse(answer)
        

        if not duration:
            await new_ictx.respond("Invalid duration. Use something like 3 weeks or 20 days", update=True)
            return
        
        ctx = miru.ViewContext(self, client, new_ictx.interaction)
        self.menu._last_context = ctx
        self._last_context = ctx
        
        self.table[self.selected_row_index].duration = timedelta(seconds=duration)
        await self.menu.update_message()

    # save button
    @menu.button(emoji="💾", label="Save", style=ButtonStyle.SECONDARY, custom_id="autoroles_save", row=2)
    async def button_save(self, ctx: miru.ViewContext, button: menu.ScreenButton):
        await ctx.respond("Start..", flags=hikari.MessageFlag.EPHEMERAL)
        await self.save_rows()
        await ctx.edit_response("Saved!", flags=hikari.MessageFlag.EPHEMERAL)
        
    @menu.button(emoji="❌", label="Stop", style=ButtonStyle.SECONDARY, custom_id="autoroles_close")
    async def button_close(self, ctx: miru.ViewContext, button: menu.ScreenButton):
        self.menu.stop()
        await (await ctx.get_last_response()).delete()

    async def save_rows(self):
        for row in self.table:
            saved = await row.save()
            log.trace(f"{saved=}; {row=}")

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
        records.sort(key=lambda x: x["expires_at"], reverse=True)
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