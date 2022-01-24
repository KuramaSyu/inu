from typing import *
from enum import Enum
from pprint import pprint
import random

import hikari
from hikari import ButtonStyle, ComponentInteraction, Embed
from hikari.impl import ActionRowBuilder
from numpy import sort
from common import *
from common import listener


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
    ):
        super().__init__(page_s)

    def build_default_components(self, position=None) -> Optional[List[Optional[ActionRowBuilder]]]:
        components = super().build_default_components(position)
        if not isinstance(components, list):
            return components
        components[-1] = components[-1].add_button(ButtonStyle.SECONDARY, "btn_anime_sort").set_label("sort").add_to_container()
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