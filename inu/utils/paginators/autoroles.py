from typing import *

from tabulate import tabulate
import hikari
from hikari import ComponentInteraction, ButtonStyle
from hikari.impl import MessageActionRowBuilder

from . import Paginator
from ..db import AutoroleManager, AutoroleBuilder


class AutorolesPaginator(Paginator):
    table_headers = ["ID", "Role", "Event", "duration"]
    table: List[AutoroleBuilder] = []

    async def build_default_components(self, position=None) -> List[MessageActionRowBuilder]:
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