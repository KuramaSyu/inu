from typing import *
from enum import Enum
from pprint import pprint
import random
import traceback
from pprint import pformat
from copy import deepcopy

import hikari
from hikari import ButtonStyle, ComponentInteraction, Embed
from hikari.impl import ActionRowBuilder
import lightbulb
from numpy import longdouble, sort
from pyparsing import CloseMatch

from .common import PaginatorReadyEvent
from .common import Paginator
from .common import listener
from jikanpy import AioJikan
from lightbulb.context import Context
from fuzzywuzzy import fuzz

from core import getLogger
from utils import Human, Colors, MyAnimeList, Anime

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
            pass
            components[-1] = components[-1].add_button(ButtonStyle.SECONDARY, "btn_anime_re_search").set_label("show more").add_to_container()
        # add more information button
        components[-1] = components[-1].add_button(ButtonStyle.SECONDARY, "btn_anime_more_info").set_label("show more").add_to_container()
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
        elif event.interaction.custom_id == "btn_anime_more_info":
            await self._update_position(event.interaction, detailed=True)
            return

    def _sort_embeds(self, sort_by: SortTypes):
        self._pages = sort_by(self._pages)

    async def start(self, ctx: Context, anime_name: str) -> hikari.Message:
        self.ctx = ctx
        self._pages = await self._search_anime(anime_name)
        self._position = 0
        await self._load_details()
        super().__init__(page_s=self._pages, timeout=10*8)
        return await super().start(ctx)

    async def _update_position(self, interaction: ComponentInteraction, detailed=False):
        """
        replaces embed page first with a more detailed one, before sending the message
        """
        await self._load_details(detailed=detailed)
        return await super()._update_position(interaction)

    def _fuzzy_sort_results(self, compare_name: str):
        """fuzzy sort the anime result titles of  `self._results` by given name"""
        close_matches = []
        for anime in self._results.copy():
            anime["fuzz_ratio"] = fuzz.ratio(anime["title"].lower(), compare_name.lower())
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
                if search_title.lower() in anime["title"].lower():
                    animes.append(anime)

            if animes == []:
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

    async def _fetch_anime_by_id(self, mal_id: int) -> Anime:
        """Fetch a detailed anime dict by mal_id"""
        return await MyAnimeList.fetch_anime_by_id(mal_id)
    
    async def _load_details(self, detailed=False) -> List[hikari.Embed]:
        """
        updates the embed `self._pages[self._position]` to a more detailed version of the anime
        """
        mal_id = self._results[self._position]["mal_id"]
        if mal_id in self._updated_mal_ids and not detailed:
            return
        self._updated_mal_ids.add(mal_id)
        if not (anime := self._results[self._position].get("anime")):
            anime = await self._fetch_anime_by_id(mal_id)
            self._results[self._position]["anime"] = anime
        old_embed = self._pages[self._position]
        
        popularity = ""
        if anime.popularity <= 100:
            popularity = f"very popular | {anime.popularity}"
        elif anime.popularity <= 250:
            popularity = f"well known | {anime.popularity}"
        elif anime.popularity <= 350:
            popularity = f"known | {anime.popularity}"
        elif anime.popularity <= 1000:
            popularity = f"somewhat known | {anime.popularity}"
        else:
            popularity = anime.popularity
        embed = (
            hikari.Embed()
            .add_field("Type", anime.type_, inline=True)
            .add_field("Score", f"{anime.score}/10", inline=True)
            .add_field("Episodes", f"{anime.episodes} {Human.plural_('episode', anime.episodes)}", inline=True)
            .add_field("Rank", f"{anime.rank}", inline=True)
            .add_field("Popularity", popularity, inline=True)
            .add_field("Rating", f"{anime.rating}", inline=True)
            .add_field("Duration", f"{anime.duration}", inline=True)


            .set_image(anime.image_url)
        )
        if anime.genres:
            embed.add_field(
                "Genres",
                anime.markup_link_str(anime.all_genres),
                inline=True,
            )
        if anime.themes:
            embed.add_field(
                "Themes",
                anime.markup_link_str(anime.themes),
                inline=True,
            )
        # if anime.trailer_url:
        #     embed.add_field("Trailer", f"[click here]({anime.trailer_url})", inline=True)
        if anime.studios:
            embed.add_field(
                "Studios", 
                anime.markup_link_str(anime.studios),
                inline=True
            )
        # if anime.producers:
        #     embed.add_field(
        #         "Producers", 
        #         anime.markup_link_str(anime.producers),
        #         inline=True
        #     )
        if anime.licensors:
            embed.add_field(
                "Licensors", 
                anime.markup_link_str(anime.licensors),
                inline=True
            )
        if anime.title_synonyms:
            synonyms = ",\n".join(anime.title_synonyms)
            embed.add_field(
                "Synonyms", 
                synonyms,
                inline=len(synonyms) < 80,
            )
        embed.add_field("finished", f"{Human.bool_(anime.is_finished)}\n{anime.airing_str}", inline=True)
        embed.description = ""
        embed.title = anime.title

        if anime.title != anime.origin_title:
            embed.description += f"original name: {anime.origin_title}"
        embed.description += f"\nmore information on [MyAnimeList]({anime.mal_url})"
        media = (
            f"Watch: "
            f"[sub]({anime.links.get('animeheaven-sub')}) "
            f"| [dub]({anime.links.get('animeheaven-dub')})"
        )
        if anime.trailer_url:
            media += f" | [trailer]({anime.trailer_url})"
        embed.description += f"\n{media}"
        embed.description += f"\n\n{Human.short_text(anime.synopsis, 1980)}"

        related_str = ""
        always_used = ["Prequel", "Sequel", "Adaption"]
        log.debug(f"{detailed=}")
        for name, info in anime.related.items():
            # related contains a dict, with sequel, prequel, adaption and sidestory. 
            # Every entry of the dict has as value a list, which contains dicts. 
            # Every dict in there represents one of wahtever the name of the value is
            if not name in always_used and not detailed:
                continue

            related_str =""
            if name == "Sequel":
                name = "Sequel (watch after)"
            elif name == "Prequel":
                name = "Prequel (watch before)"
            for i in info:
                # check if i (dict) contains name and url as keys
                if set(["name", "url"]) <= (keys := set([*i.keys()])):

                    if "type" in keys:
                        related_str += f"{i['type']}: "
                    related_str += f"{anime.markup_link_str([i])}\n"
            embed.add_field(name, related_str, inline=len(related_str) < 180)
        
        # watch_here_str = "\n".join([f"[{s}]({l})" for s, l in anime.links.items()])
        # embed.add_field("Watch here", watch_here_str, inline=True)
        if anime.background and detailed:
            embed.add_field("Background", Human.short_text(anime.background, 200))

        # add openings if not too much
        # TODO: remove redundant code in this function
        # TODO: add mal database table to don't spam requests
        # TODO: if no anime was found (404), send message and stop paginating


        if (len_openings := len(anime.opening_themes)) > 5:
            embed.add_field("Opening themes", f"Too many to show here ({len_openings})")
        elif len_openings == 0:
            pass
        else:
            embed.add_field("Opening themes", "\n".join(anime.opening_themes))

        # add endings if not too much
        if (len_endings := len(anime.ending_themes)) > 5:
            embed.add_field("Ending themes", f"Too many to show here ({len_openings})")
        elif len_endings == 0:
            pass
        else:
            embed.add_field("Ending themes", "\n".join(anime.ending_themes))

        
        for i, field in enumerate(embed.fields):
            if not field.value:
                embed.remove_field(i)
            field.value = Human.short_text(field.value, 1024)
        # optimizing space
        inline_fields = []
        outline_fields = []
        for field in embed.fields:
            if field.is_inline:
                inline_fields.append(field)
            else:
                outline_fields.append(field)
        embed._fields = [*inline_fields, *outline_fields]
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