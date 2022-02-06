from typing import *
from enum import Enum
from pprint import pprint
import random
import traceback
from pprint import pformat

import hikari
from hikari import ButtonStyle, ComponentInteraction, Embed
from hikari.impl import ActionRowBuilder
import lightbulb
from numpy import sort
from pyparsing import CloseMatch
from .common import PaginatorReadyEvent
from .common import Paginator
from .common import listener
from jikanpy import AioJikan
from lightbulb.context import Context
from fuzzywuzzy import fuzz

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


class AnimePaginator(Paginator):
    def __init__(
        self,
        with_refresh_btn: bool = False,
        old_message = None,
    ):
        self._old_message = old_message
        self._with_refresh_btn = with_refresh_btn

        self._results: List[Dict]
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

    async def start(self, ctx: Context, anime_name: str) -> hikari.Message:
        self.ctx = ctx
        self._pages = await self._search_anime(anime_name)
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

    def _fuzzy_sort_results(self, compare_name: str):
        """fuzzy sort the anime result titles of  `self._results` by given name"""
        close_matches = []
        for anime in self._results.copy():
            anime["fuzz_ratio"] = fuzz.ratio(anime["title"].lower(), compare_name)
            if anime["fuzz_ratio"] >= 90:
                self._results.remove(anime)
                close_matches.append(anime)
        close_matches.sort(key=lambda anime: anime["fuzz_ratio"], reverse=True)
        self._results = [*close_matches, *self._results]

    async def _search_anime(self, search: str) -> List[hikari.Embed]:
        """Search <`search`> anime, and set results to `self._results`. These have less information"""
        def build_embeds(search_title: str, results: Dict):
            animes = []
            for anime in results:
                if search_title in anime["title"].lower():
                    animes.append(anime)

            if animes == []:
                log.debug("filter animes by name")
                animes = results

            embeds = []
            total = len(animes)
            for i, anime in enumerate(animes):
                embeds.append(
                    (
                        hikari.Embed(
                            title=anime["title"],
                            description=f"more information on [MyAnimeList]({anime['url']})"
                        )
                        .add_field("Type", anime["type"], inline=True)
                        .add_field("Score", f"{anime['score']}/10", inline=True)
                        .add_field("Episodes", f"{anime['episodes']} {Human.plural_('episode', anime['episodes'])[0]}", inline=True)
                        .add_field("Description", anime['synopsis'] or "No description", inline=False)
                        .add_field(
                            "Other",
                            (
                                f"finished: {Human.bool_('airing')}\n"
                                f"Members: {anime['members']}\n"
                                f"MyAnimeList ID: {anime['mal_id']}\n"
                                f"rated: {anime['rated']}\n"
                                f"start date: {anime['start_date'][:10] if anime['start_date'] else 'unknown'}\n"
                                f"end date: {anime['end_date'][:10] if anime['end_date'] else 'unknown'}\n"

                            )
                        )
                        .set_image(anime["image_url"])
                        .set_footer(text=f"page {i+1}/{total}")
                    )
                )
            return embeds

        results = None

        async with AioJikan() as aio_jikan:
            results = await aio_jikan.search(search_type='anime', query=search)
        # store result list
        self._results = results["results"]
        # sort the list by comparing with given name
        self._fuzzy_sort_results(search)
        # build embeds out of 
        embeds = build_embeds(search, self._results)
        if not embeds:
            return [hikari.Embed(title="Nothing found")]
        return embeds

    async def _fetch_anime_by_id(self, mal_id: int) -> Dict:
        """Fetch a detailed anime dict by mal_id"""
        async with AioJikan() as jikan:
            anime = await jikan.anime(mal_id)
        return anime
    
    async def _load_details(self) -> List[hikari.Embed]:
        """
        updates the embed `self._pages[self._position]` to a more detailed version of the anime
        """
        mal_id = self._results[self._position]["mal_id"]
        if mal_id in self._updated_mal_ids:
            return
        self._updated_mal_ids.add(mal_id)
        anime = await self._fetch_anime_by_id(mal_id)
        old_embed = self._pages[self._position]
        
        popularity = ""
        if anime['popularity'] <= 100:
            popularity = f"very popular | {anime['popularity']}"
        elif anime['popularity'] <= 250:
            popularity = f"well known | {anime['popularity']}"
        elif anime['popularity'] <= 350:
            popularity = f"known | {anime['popularity']}"
        elif anime['popularity'] <= 1000:
            popularity = f"somewhat known | {anime['popularity']}"
        else:
            popularity = anime['popularity']
        embed = (
            hikari.Embed()
            .add_field("Type", anime["type"], inline=True)
            .add_field("Score", f"{anime['score']}/10", inline=True)
            .add_field("Episodes", f"{anime['episodes']} {Human.plural_('episode', anime['episodes'])[0]}", inline=True)
            .add_field("Rank", f"{anime['rank']}", inline=True)
            .add_field("Popularity", popularity, inline=True)
            .add_field("Rating", f"{anime['rating']}", inline=True)
            .add_field("Duration", f"{anime['duration']}", inline=True)


            .set_image(anime["image_url"])
        )
        if anime["genres"]:
            embed.add_field(
                "Genres",
                f""" {', '.join(f"[{genre['name']}]({genre['url']})" 
                for genre in anime["genres"])}, {', '.join(f"[{genre['name']}]({genre['url']})" 
                for genre in anime["explicit_genres"])}
                """,
                inline=True,
            )
        if anime["themes"]:
            embed.add_field(
                "Themes",
                ", ".join(
                    f"[{theme['name']}]({theme['url']})" for theme in anime["themes"]
                ),
                inline=True,
            )
        if anime["trailer_url"]:
            embed.add_field("Trailer", f"[click here]({anime['trailer_url']})", inline=True)
        if anime["studios"]:
            embed.add_field(
                "Studios", 
                ", ".join(f"[{studio['name']}]({studio['url']})" for studio in anime["studios"]),
                inline=True
            )
        if anime["producers"]:
            embed.add_field(
                "Producers", 
                ", ".join(f"[{producer['name']}]({producer['url']})" for producer in anime["producers"]),
                inline=True
            )
        if anime["licensors"]:
            embed.add_field(
                "Licensors", 
                ", ".join(f"[{licensor['name']}]({licensor['url']})" for licensor in anime["licensors"]),
                inline=True
            )
        if anime["title_synonyms"]:
            embed.add_field(
                "Synonyms", 
                ",\n".join(anime["title_synonyms"]),
                inline=True
            )
        embed.add_field("finished", f"{Human.bool_('airing')}\n{anime['aired']['string']}", inline=True)

        embed.description = ""
        embed.title = ""
        if anime["title"] == anime["title_english"]:
            embed.title = anime["title"]
        elif anime["title_english"]:
            embed.title = anime["title_english"]
        else:
            embed.title = anime["title"]

            embed.description += f"original name: {anime['title']}"
        embed.description += f"\nmore information on [MyAnimeList]({anime['url']})"
        embed.description += f"\n\n{Human.short_text(anime['synopsis'], 1980)}"

        if anime["background"]:
            embed.add_field("Background", Human.short_text(anime["background"], 200))

        # add openings if not too much
        # TODO: remove redundant code in this function
        # TODO: add mal database table to don't spam requests
        # TODO: if no anime was found (404), send message and stop paginating


        if (len_openings := len(anime["opening_themes"])) > 5:
            embed.add_field("Opening themes", f"Too many to show here ({len_openings})")
        elif len_openings == 0:
            pass
            pass
        else:
            embed.add_field("Opening themes", "\n".join(anime["opening_themes"]))

        # add endings if not too much
        if (len_endings := len(anime["ending_themes"])) > 5:
            embed.add_field("Ending themes", f"Too many to show here ({len_openings})")
        elif len_endings == 0:
            pass
        else:
            embed.add_field("Ending themes", "\n".join(anime["ending_themes"]))

        for i, field in enumerate(embed.fields):
            if not field.value:
                embed.remove_field(i)
            field.value = Human.short_text(field.value, 1024)
        embed._footer = old_embed._footer
        self._pages[self._position] = embed


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