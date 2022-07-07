from typing import *
from enum import Enum
from pprint import pprint
import random
import traceback
from pprint import pformat
from copy import deepcopy

import hikari
from hikari import ButtonStyle, ComponentInteraction, Embed, ResponseType
from hikari.impl import ActionRowBuilder
import lightbulb
from numpy import longdouble, sort
from pyparsing import CloseMatch

from .base import PaginatorReadyEvent, Paginator, listener
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
        super().__init__(page_s=["None"], timeout=60*2)
        

    def build_default_components(self, position=None) -> Optional[List[Optional[ActionRowBuilder]]]:
        components = super().build_default_components(position)
        if not isinstance(components, list):
            return components
        # components[-1] = components[-1].add_button(ButtonStyle.SECONDARY, "btn_anime_sort").set_label("sort by score").add_to_container()
        if self._with_refresh_btn:
            pass
            components[-1] = components[-1].add_button(ButtonStyle.SECONDARY, "btn_anime_re_search").set_label("show more").add_to_container()
        # add more information button
        components[-1] = (
            components[-1]
            .add_button(ButtonStyle.SECONDARY, "btn_anime_more_info")
            .set_label("details").add_to_container()
            .add_button(ButtonStyle.SECONDARY, "btn_anime_openings")
            .set_label("all openings").add_to_container()
            .add_button(ButtonStyle.SECONDARY, "btn_anime_endings")
            .set_label("all endings").add_to_container()

        )
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
        elif event.interaction.custom_id == "btn_anime_openings":
            return await self._send_openings(interaction=event.interaction)
        elif event.interaction.custom_id == "btn_anime_endings":
            return await self._send_endings(interaction=event.interaction)
        

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
            anime["fuzz_ratio"] = fuzz.ratio(anime["node"]["title"].lower(), compare_name.lower())
            if anime["fuzz_ratio"] >= 80:
                self._results.remove(anime)
                close_matches.append(anime)
        close_matches.sort(key=lambda anime: anime["fuzz_ratio"], reverse=True)
        self._results = [*close_matches, *self._results]

    async def _search_anime(self, search: str) -> List[hikari.Embed]:
        """Search <`search`> anime, and set results to `self._results`. These have less information"""
        def build_embeds(search_title: str, results: Dict):
            animes: List[Dict[str, Any]] = []

            # sort by name
            for anime in results:
                if (
                    (name := search_title.lower()) in anime["node"]["title"].lower()
                    or name in anime["node"]["alternative_titles"].get("en", "").lower()
                    or name in anime["node"]["alternative_titles"].get("ja", "").lower()
                    or [title for title in anime["node"]["alternative_titles"].get("synonyms", []) if name in title.lower()]
                ):
                    animes.append(anime)

            if animes == []:
                animes = results

            embeds = []
            total = len(animes)
            for i, anime in enumerate(animes):
                embeds.append(
                    (
                        hikari.Embed(
                            title=anime["node"]["title"],
                        )
                        .set_footer(text=f"page {i+1}/{total} | {anime['node']['title']}")
                    )
                )
            return embeds

        results = await MyAnimeList.search_anime(query=search)
        # store result list
        self._results = results["data"]
        # sort the list by comparing with given name
        self._fuzzy_sort_results(search)
        # build embeds out of 
        embeds = build_embeds(search, self._results)
        if not embeds:
            return [hikari.Embed(title="Nothing found")]
        return embeds

    async def _fetch_current_anime(self) -> Anime:
        """Fetches or returns already fetched anime"""
        # fetch anime if not done yet
        mal_id = self._results[self._position]["node"]["id"]
        anime: Anime
        if not (anime := self._results[self._position].get("anime")):
            anime = await MyAnimeList.fetch_anime_by_id(mal_id)
            self._results[self._position]["anime"] = anime
        log.debug(f"fetched anime: {anime}")
        return anime

    async def _load_details(self, detailed=False) -> None:
        """
        updates the embed `self._pages[self._position]` to a more detailed version of the anime
        """
        # fetch anime if not done yet
        anime = await self._fetch_current_anime()

        old_embed = self._pages[self._position]
        
        # build detailed embed
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
            .add_field("Duration", f"{anime.duration / 60:.1f} min per episode", inline=True)
            .set_image(anime.image_url)
        )
        if anime.genres:
            embed.add_field(
                "Genres",
                ", ".join(anime.genres),
                inline=True,
            )
        if anime.studios and detailed:
            embed.add_field(
                "Studios", 
                ", ".join(anime.studios),
                inline=True
            )
        if anime.title_synonyms:
            synonyms = ",\n".join(anime.title_synonyms)
            embed.add_field(
                "Synonyms", 
                synonyms,
                inline=len(synonyms) < 80,
            )
        embed.add_field(
            "Info",
            anime.airing_str,
            inline=True
        )
        if detailed:
            embed.add_field(
                "Recommendations",
                f"{anime.markup_link_str(anime.recommendations)}",
                inline=True,
            )

        embed.description = ""
        embed.title = anime.title

        if anime.title != anime.origin_title:
            embed.description += f"original name: {anime.origin_title}"
        embed.description += f"\nmore information on [MyAnimeList]({anime.mal_url})"
        embed.description += f"\n\n{Human.short_text(anime.synopsis, 1980 if detailed else 150)}"

        related_str = ""
        always_used = ["prequel", "sequel", "full_story"]
        for relation_type, relations in anime.related.items():
            # related contains dict with mapping from relation_type to list of relations
            # one relation is a node with keys "mal_id", "title", "type", "mal_url"..
            related_str =""
            fmt_relation = ""
            if relation_type == "sequel":
                fmt_relation = "Sequel (watch after)"
            elif relation_type == "prequel":
                fmt_relation = "Prequel (watch before)"
            elif relation_type == "full_story":
                fmt_relation = "Full story"
            else:
                fmt_relation = relations[0].get(
                    "relation_type_formatted", relation_type.replace("_", " ")
                )

            for node in relations:
                relation = node["relation_type"]
                if not relation in always_used and not detailed:
                    continue
                related_str += f"{node['type']}: [{node['title']}]({node['url']})\n"
            if related_str and fmt_relation:
                embed.add_field(
                    fmt_relation, 
                    related_str, 
                    inline=len(related_str) < 180
                )
        
        if anime.background and detailed:
            embed.add_field("Background", Human.short_text(anime.background, 200))

        if (len_openings := len(anime.opening_themes)) > 4:
            embed.add_field("Opening themes", f"Too many to show here ({len_openings})", inline=True)
        elif len_openings == 0:
            pass
        else:
            embed.add_field("Opening themes", "\n".join(anime.opening_themes))

        if detailed:
            embed.add_field("Completion rate", f"{anime.completion_rate}", inline=True)

        # add endings if not too much
        if (len_endings := len(anime.ending_themes)) > 3:
            embed.add_field("Ending themes", f"Too many to show here ({len_openings})", inline=True)
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
    
    async def _send_openings(self, interaction: hikari.ComponentInteraction):
        # fetch anime if not done yet
        anime = await self._fetch_current_anime()

        embed = hikari.Embed(
            title=f"Openings from {anime.title}",
            description="\n".join(anime.opening_themes),
        )
        embed.color = Colors.random_blue()
        return await interaction.create_initial_response(ResponseType.MESSAGE_CREATE, embed=embed)

    async def _send_endings(self, interaction: hikari.ComponentInteraction):
        # fetch anime if not done yet
        anime = await self._fetch_current_anime()
        embed = hikari.Embed(
            title=f"Endings from {anime.title}",
            description="\n".join(anime.ending_themes),
        )
        embed.color = Colors.random_blue()
        return await interaction.create_initial_response(ResponseType.MESSAGE_CREATE, embed=embed)


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