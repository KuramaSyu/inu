from typing import *
from enum import Enum
from pprint import pprint
import random
import traceback

import hikari
from hikari import ButtonStyle, ComponentInteraction, Embed
from hikari.impl import ActionRowBuilder
import lightbulb
from numpy import sort
from .common import PaginatorReadyEvent
from .common import Paginator
from .common import listener

from core import getLogger

log = getLogger(__name__)


class SortBy:
    @staticmethod
    def by_score(embeds: List[Embed]) -> float:
        def get_embed_score(embed: Embed):
            try:
                value = [f for f in embed.fields if f.name == "Score"][0].value
            except IndexError:
                raise RuntimeError(
                    "No field with name Score!: Embeds for `AnimePaginator` need field with name=Score and value=<num>/<num>"
                )
            try:
                score, _ = value.split("/")
            except Exception:
                raise RuntimeError("The field value of the field with name=Score needs to look like this: <score>/<max>")
            return float(score)

        embeds = embeds.copy()
        embeds.sort(key=get_embed_score, reverse=True)
        return embeds


class SortTypes(Enum):
    BY_SCORE = SortBy.by_score


class AnimePaginator(Paginator):
    def __init__(
        self,
        page_s: Union[List[str], List[Embed]],
        with_refresh_btn: bool = False,
        old_message: Optional[lightbulb.ResponseProxy] = None,
    ):
        self._old_message = old_message
        self._with_refresh_btn = with_refresh_btn
        super().__init__(page_s=page_s, timeout=10*8)

    def build_default_components(self, position=None) -> Optional[List[Optional[ActionRowBuilder]]]:
        components = super().build_default_components(position)
        if not isinstance(components, list):
            return components
        #components[-1] = components[-1].add_button(ButtonStyle.SECONDARY, "btn_anime_sort").set_label("sort").add_to_container()
        if self._with_refresh_btn:
            components[-1] = components[-1].add_button(ButtonStyle.SECONDARY, "btn_anime_re_search").set_label("more information").add_to_container()
        return components
    
    @listener(hikari.InteractionCreateEvent)
    async def on_component_interaction(self, event: hikari.InteractionCreateEvent):
        if not isinstance(event.interaction, ComponentInteraction):
            return
        if event.interaction.custom_id == "btn_anime_sort":
            self._sort_embeds(SortTypes.BY_SCORE)
            self._position = 0
            await self.send(self._pages[self._position], interaction=event.interaction)
            return
        elif event.interaction.custom_id == "btn_anime_re_search":
            self._stop = True
            if self._old_message:
                await self._old_message.delete()
            await self.bot.rest.delete_messages(self.ctx.channel_id, [self._message.id])
            try:
                ext = self.bot.get_plugin("Anime")
                for cmd in ext.all_commands:
                    if cmd.name == "anime":
                        self.ctx._options["name"] = self.pages[self._position].title
                        await cmd.callback(self.ctx)
                        return
            except:
                log.error(traceback.format_exc())

    def _sort_embeds(self, sort_by: SortTypes):
        self._pages = sort_by(self._pages)

if __name__ == "__main__":
    embeds = []
    for _ in range(10):
        embeds.append(
            Embed(title="test").add_field("Score", f"{random.randrange(0, 10)}/10")
        )
    pag = AnimePaginator(page_s=embeds)
    pag._sort_embeds(SortTypes.BY_SCORE)
    for e in pag._pages:
        print(e.fields)