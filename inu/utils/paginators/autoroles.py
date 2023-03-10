from typing import *

from tabulate import tabulate
import hikari
from hikari import ComponentInteraction
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
            .add_button(
        )

    async def render(self):
        ...

    async def _update_position(self, interaction: ComponentInteraction | None = None,):
        """
        replaces embed page first with a more detailed one, before sending the message
        """
        await self.render()
        await super()._update_position(interaction)