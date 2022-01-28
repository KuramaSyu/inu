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
from hikari.impl import ActionRowBuilder
import lightbulb
from .common import PaginatorReadyEvent
from .common import Paginator
from .common import listener
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


class AnimeCharacterPaginator(Paginator):
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
        

    def build_default_components(self, position=None) -> Optional[List[Optional[ActionRowBuilder]]]:
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
                    if cmd.name == "anime":
                        self.ctx._options["name"] = self.pages[self._position].title
                        await cmd.callback(self.ctx)
                        return
            except:
                log.error(traceback.format_exc())

    def _sort_embeds(self, sort_by: SortTypes):
        self._pages = sort_by(self._pages)

    async def start(self, ctx: Context, character_name: str) -> hikari.Message:
        self.ctx = ctx
        self._pages = await self._search_anime(character_name)
        self._position = 0
        await self._load_details()
        super().__init__(page_s=self._pages, timeout=10*8)
        return await super().start(ctx)

    async def _update_position(self, interaction: ComponentInteraction):
        """
        replaces embed page first with a more detailed one, before sending the message
        """
        await self._load_details()
        return await super()._update_position(interaction)

    async def _search_anime(self, search: str) -> List[hikari.Embed]:
        def build_embeds(search_title: str, results: Dict):
            animes = []
            for anime in results["results"]:
                if search_title in anime["name"]:
                    animes.append(anime)

            if animes == []:
                animes = results['results']

            embeds = []
            total = len(animes)
            for i, anime in enumerate(animes):
                embed = Embed(title="anime-character")
                embed.set_footer(f"page {i+1}/{total}")
                embeds.append(embed)
            return embeds

        results = None

        async with AioJikan() as aio_jikan:
            results = await aio_jikan.search(search_type='character', query=search)
        self._results = results["results"]
        embeds = build_embeds(search, results)
        if not embeds:
            return [hikari.Embed(title="Nothing found")]
        return embeds

    async def _fetch_character_by_id(self, mal_id: int) -> Dict:
        """Fetch a detailed anime dict by mal_id"""
        async with AioJikan() as jikan:

            result = await asyncio.wait_for(jikan.character(mal_id), 0.9)
        return result
    
    async def _load_details(self) -> List[hikari.Embed]:
        """
        updates the embed `self._pages[self._position]` to a more detailed version of the anime
        """
        mal_id = self._results[self._position]["mal_id"]
        if mal_id in self._updated_mal_ids:
            return
        self._updated_mal_ids.add(mal_id)
        old_embed = self._pages[self._position]
        try:
            anime = await self._fetch_character_by_id(mal_id)
            embed = (
                hikari.Embed()
                .set_image(anime["image_url"])
            )
            with suppress(Exception):
                embed.add_field("Anime", anime["animeography"][0]["name"], inline=True)
                embed.add_field("role", anime["animeography"][0]["role"], inline=True)
                embed.add_field("Voice actors", Human.short_text("\n".join(
                            f"{actor['language']}: [{actor['name']}]({actor['url']})"
                            for actor in anime["voice_actors"]
                        ),
                        1000
                    )
                )
            embed.description = ""
            embed.title = anime["name"]

            if anime["nicknames"]:
                embed.description += f"aliases: {', '.join(anime['nicknames'])}"
            embed.description += f"\nmore information on [MyAnimeList]({anime['url']})"
            embed.description += f"\n\n{Human.short_text(anime['about'], 1980)}"
        except Exception:
            log.warning(f"in AnimeCharacterPaginator._load_details(): {traceback.format_exc()}")
            info = self._results[self._position]
            embed = Embed(title=info["name"])
            embed.description = ""
            embed.description += f"\nmore information on [MyAnimeList]({info['url']})"
            embed.set_image(info["image_url"])
            with suppress(Exception):
                embed.add_field("Anime", ", ".join(info["anime"]))
                embed.add_field("Alternative Names", ", ".join(info["alternative_names"]))

        for i, field in enumerate(embed.fields):
            if not field.value:
                embed.remove_field(i)
        embed._footer = old_embed._footer
        self._pages[self._position] = embed


