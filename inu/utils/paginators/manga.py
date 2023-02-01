from contextlib import suppress
from typing import *
from enum import Enum
from pprint import pprint
import random
import traceback
from pprint import pformat
from async_timeout import asyncio

import hikari
from hikari import ButtonStyle, ComponentInteraction, Embed
from hikari.impl import MessageActionRowBuilder
import lightbulb
from .base import PaginatorReadyEvent, Paginator, listener
from jikanpy import AioJikan
from lightbulb.context import Context

from core import getLogger
from utils import Human, Colors

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


class MangaPaginator(Paginator):
    def __init__(
        self,
        with_refresh_btn: bool = False,
        old_message = None,
    ):
        self._old_message = old_message
        self._with_refresh_btn = with_refresh_btn

        self._results = None
        self._updated_mal_ids = set()
        super().__init__(page_s=["None"], timeout=10*8)
        

    def build_default_components(self, position=None) -> Optional[List[Optional[MessageActionRowBuilder]]]:
        components = super().build_default_components(position)
        if not isinstance(components, list):
            return components
        # components[-1] = components[-1].add_button(ButtonStyle.SECONDARY, "btn_anime_sort").set_label("sort by score").add_to_container()
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
                    if cmd.name == "manga":
                        self.ctx._options["name"] = self.pages[self._position].title
                        await cmd.callback(self.ctx)
                        return
            except:
                log.error(traceback.format_exc())

    def _sort_embeds(self, sort_by: SortTypes):
        self._pages = sort_by(self._pages)

    async def start(self, ctx: Context, character_name: str) -> hikari.Message:
        self.ctx = ctx
        self._pages = await self._search_manga(character_name)
        self._position = 0
        super().__init__(page_s=self._pages, timeout=10*8)
        return await super().start(ctx)


    async def _search_manga(self, search: str) -> List[hikari.Embed]:
        def build_embeds(search_title: str, results: Dict):
            mangas = []
            for manga in results["results"]:
                if search_title.lower() in manga["title"].lower():
                    mangas.append(manga)

            if manga == []:
                mangas = results['results']

            embeds = []
            total = len(mangas)
            for i, manga in enumerate(mangas):
                embed = Embed(title=manga["title"])
                embed.description = f"More information on [MyAnimeList]({manga['url']})\n\n"
                embed.description += Human.short_text(manga["synopsis"], 2000)
                embed.add_field("Chapters", manga["chapters"], inline=True)
                embed.add_field("Score", manga["score"], inline=True)
                embed.add_field("Volumes", manga["volumes"], inline=True)
                embed.add_field("Type", manga["type"], inline=True)
                embed.add_field(
                    "Information",
                    (
                        f'still in production: {Human.bool_(manga["publishing"])}\n'
                        f'{str(manga["start_date"])[:4]} - {str(manga["end_date"])[:4]}'
                    ),
                    inline=True
                )
                embed.set_image(manga["image_url"])
                embed.set_footer(f"page {i+1}/{total}")
                embeds.append(embed)
            return embeds

        results = None

        async with AioJikan() as aio_jikan:
            results = await aio_jikan.search(search_type='manga', query=search)
        self._results = results["results"]
        embeds = build_embeds(search, results)
        if not embeds:
            return [hikari.Embed(title="Nothing found")]
        return embeds

    async def _fetch_character_by_id(self, mal_id: int) -> Dict:
        """Fetch a detailed manga dict by mal_id"""
        async with AioJikan() as jikan:
            result = await asyncio.wait_for(jikan.character(mal_id), 0.9)
        return result
    

        for i, field in enumerate(embed.fields):
            if not field.value:
                embed.remove_field(i)
        embed._footer = old_embed._footer
        self._pages[self._position] = embed


