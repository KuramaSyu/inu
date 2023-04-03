from typing import *
from datetime import datetime, timedelta
import asyncio

from tabulate import tabulate
import hikari
from hikari import ComponentInteraction, ButtonStyle
from hikari.impl import MessageActionRowBuilder
import miru
from pytimeparse.timeparse import timeparse
from humanize import naturaldelta

from . import Paginator
from ..db import AutoroleManager, AutoroleBuilder, AutoroleEvent

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
        log.debug(self.roles)
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
    
    async def pre_start(self, guild_id: int):
        self.table = await AutoroleManager.wrap_events_in_builder(
            await AutoroleManager.fetch_events(guild_id, None)
        )
        log.debug(self.table)
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
        builder.guild = self.last_context.guild_id
        self.table.insert(self.selected_row_index, builder)
        await self.render_table()

    @miru.button(label="➖", style=ButtonStyle.SECONDARY, custom_id="autoroles_remove")
    async def button_remove(self, button: miru.Button, ctx: miru.ViewContext):
        event = self.table.pop(self.selected_row_index)
        await event.delete()
        await self.render_table()

    @miru.button(emoji="📌", label="Set Role", style=ButtonStyle.SECONDARY, custom_id="autoroles_set_role", row=2)
    async def button_set_role(self, button: miru.Button, ctx: miru.ViewContext):
        role_select = RoleSelectView(ctx.author.id)
        msg = await ctx.edit_response(components=role_select)
        await role_select.start(await msg.retrieve_message())
        await role_select.wait()
        #await msg.delete()
        log.debug(role_select.roles)
        if not role_select.roles:
            return
        await self.start(await msg.retrieve_message())
        self.table[self.selected_row_index].role = role_select.roles[0]
        log.debug(self.table[self.selected_row_index].role_id)
        await self.render_table()


    @miru.button(emoji="📅", label="Set Event", style=ButtonStyle.SECONDARY, custom_id="autoroles_set_event", row=2)
    async def button_set_event(self, button: miru.Button, ctx: miru.ViewContext):
        event_select = EventSelectView(ctx.author.id)
        msg = await ctx.edit_response(components=event_select)
        await event_select.start(await msg.retrieve_message())
        await event_select.wait()
        log.debug(event_select.event)
        if not event_select.event:
            return
        await self.start(await msg.retrieve_message())
        self.table[self.selected_row_index].event = event_select.event
        log.debug(self.table[self.selected_row_index].event)
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
        #await interaction.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_CREATE, "test")
        duration = timeparse(answer)
        ctx._interaction = interaction
        if not duration:
            await ctx.respond("Invalid duration. Use something like 3 weeks or 20 days", flags=hikari.MessageFlag.EPHEMERAL)
            return
        self.table[self.selected_row_index].duration = timedelta(seconds=duration)
        await self.render_table()


    async def render_table(self):
        embed = await self.embed()
        await self.save_rows()
        await self.last_context.edit_response(embed=embed, components=self)
        #await self.last_context.respond(embed=embed) 

    async def embed(self) -> hikari.Embed:
        DEFAULT_NONE_VALUE = "---"
        table = []
        for index, row in enumerate(self.table):
            row_marker = "" if index != self.selected_row_index else ">"
            table.append([
                row_marker + str(row.id or DEFAULT_NONE_VALUE),
                str(row.role) or DEFAULT_NONE_VALUE,
                (None if not row.event else row.event.name) or DEFAULT_NONE_VALUE,
                (naturaldelta(row.duration) if row.duration else None) or DEFAULT_NONE_VALUE,
            ])
        rendered_table = tabulate(table, headers=self.table_headers, tablefmt="simple_grid", maxcolwidths=[4, 15, 15, 10])
        return hikari.Embed(
            title="Autoroles",
            description=f"```{rendered_table}```"
        )

    async def save_rows(self):
        for row in self.table:
            saved = await row.save()
            log.trace(f"{saved=}; {row=}")