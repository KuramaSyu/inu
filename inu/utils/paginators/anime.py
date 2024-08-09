import asyncio
from typing import *
from enum import Enum
from pprint import pprint
import random
import traceback
from pprint import pformat
import re
from copy import deepcopy, copy
from datetime import datetime

import hikari
from hikari import ButtonStyle, ComponentInteraction, Embed, ResponseType
from hikari.impl import MessageActionRowBuilder

import lightbulb
from numpy import longdouble, sort
from pyparsing import CloseMatch
from tabulate import tabulate

from .base import PaginatorReadyEvent, Paginator, listener
from jikanpy import AioJikan
from lightbulb.context import Context
from fuzzywuzzy import fuzz
import asyncpraw

from core.api.anime import PartialAnimeMatch, AnimeMatch
from core import getLogger, InteractionContext
from utils import Human, Colors, MyAnimeList, Anime, AnimeCornerAPI, AnimeCornerView

log = getLogger(__name__)


class SortBy:
    """
    Represents a set of functions to sort anime embeds
    """
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
                score, _ = value.strip("|").split("/")
            except Exception:
                raise RuntimeError("The field value of the field with name=Score needs to look like this: <score>/<max>")
            return float(score)

        embeds = embeds.copy()
        embeds.sort(key=get_embed_score, reverse=True)
        return embeds



class SortTypes(Enum):
    """
    Represents a list of Algorithms to sort anime embeds
    """
    BY_SCORE = SortBy.by_score



class AnimePaginator(Paginator):
    """
    Represents an anime from MyAnimeList. Either from REST or DB
    """
    def __init__(
        self,
        with_refresh_btn: bool = False,
        old_message = None,
        **kwargs
    ):
        self._old_message = old_message
        self._with_refresh_btn = with_refresh_btn

        self._results: List[Dict]
        self._updated_mal_ids = set()
        self._current_has_prequel: bool = False
        self._current_has_sequel: bool = False
        self._max_openings: int = 4
        self._max_endings: int = 4
        self._detailed: bool = False
        self._base_init_kwargs = kwargs or {}

        # re-init in start - just leave it
        super().__init__(
            page_s=["None"], 
            timeout=60*2,
        )
        

    def build_default_components(self, position=None) -> Optional[List[Optional[MessageActionRowBuilder]]]:
        components = super().build_default_components(position)
        if not isinstance(components, list):
            return components
        components: List[MessageActionRowBuilder] = [*components, MessageActionRowBuilder()]
        if len(self._pages) == 1:
            # remove pagination if there is only one page
            components.pop(0)
        if self._with_refresh_btn:
            pass
        # add more information button
        components[-1] = (
            components[-1]
            .add_interactive_button(ButtonStyle.SECONDARY, "btn_anime_more_info", label="details")
        )
        if self.has_too_many_openings:
            components[-1] = (
                components[-1]
                .add_interactive_button(ButtonStyle.SECONDARY, "btn_anime_openings", label="⤵️ openings")
            )
        if self.has_too_many_endings:
            components[-1] = (
                components[-1]
                .add_interactive_button(ButtonStyle.SECONDARY, "btn_anime_endings", label="⤵️ endings")
            )     
        if self.has_prequel:
            components[-1] = (
                components[-1]
                .add_interactive_button(ButtonStyle.SECONDARY, "btn_anime_prequel", label="⏪ Prequel")
            )
        if self.has_sequel:
            components[-1] = (
                components[-1]
                .add_interactive_button(ButtonStyle.SECONDARY, "btn_anime_sequel", label="Sequel ⏩")
            )

        if self._detailed:
            # check length of last component
            if len(components[-1]._components) >= 5:
                components.append(MessageActionRowBuilder())
            components[-1] = (
                components[-1]
                .add_interactive_button(
                    ButtonStyle.SECONDARY, 
                    "btn_anime_iterate_recommended", 
                    label="⤵️ recommendations"
                )
            )
        return components
    

    @listener(hikari.InteractionCreateEvent)
    async def on_component_interaction(self, event: hikari.InteractionCreateEvent):
        if not self.interaction_pred(event):
            return
        custom_id = event.interaction.custom_id
        i = event.interaction
        self.set_context(event=event)
        if event.interaction.custom_id == "btn_anime_sort":
            self._sort_embeds(SortTypes.BY_SCORE)
            self._position = 0
            await self.send(self._pages[self._position], interaction=event.interaction)
            return
        elif custom_id == "btn_anime_re_search":
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
        elif custom_id == "btn_anime_more_info":
            await self._update_position(event.interaction, detailed=True)
            return
        elif custom_id == "btn_anime_openings":
            return await self._send_openings(interaction=event.interaction)
        elif custom_id == "btn_anime_endings":
            return await self._send_endings(interaction=event.interaction)
        elif custom_id == "btn_anime_prequel":
            self._set_anime_id_as_next_item(self.prequel_id)
            self._position += 1
            await self._update_position(event.interaction)
        elif custom_id == "btn_anime_sequel":
            self._set_anime_id_as_next_item(self.sequel_id)
            self._position += 1
            await self._update_position(event.interaction)
        elif custom_id == "btn_anime_iterate_recommended":
            # send new message with all recommendations 
            anime = await self._fetch_current_anime()
            results: Dict[str, Dict[str, int]] = copy(anime._recommendations)
            anime_recommended_pag = AnimePaginator(
                first_message_kwargs={"content": f"Recommendations for `{anime.title}`"}
            )
            try:
                # reset interaction
                self.ctx._interaction = i
                self.ctx._responded = False
            except AttributeError:
                pass
            asyncio.create_task(
                anime_recommended_pag.start(
                    self.ctx,
                    anime_name=None,
                    results=results
                )
            )
        

    def _sort_embeds(self, sort_by: SortTypes):
        self._pages = sort_by(self._pages)


    async def start(self, ctx: Context, anime_name: str | None, results: List[Dict[str, Dict[str, int]]] | None = None) -> hikari.Message:
        """
        entry point for paginator

        Args:
        ----
        ctx : lightbulb.Context
            The context to use to send the initial message
        anime_name : str | None
            the name of the anime which should be searched
        results : List[Dict[str, Dict[str, int]]] | None
            results, if already given.
            Must use following structure:
                [
                    {"node": 
                        {"id": int}
                    }
                ]
        """
        if not anime_name and not results:
            raise RuntimeError("Either `anime_name` or `results` needs to be given. Use anime_name, when you want to search. Use results if you already have results")
        self.ctx = ctx
        self._pages = await self._search_anime(anime_name, results)
        self._position = 0
        await self._load_details()
        super().__init__(
            page_s=self._pages, 
            timeout=60*4, 
            disable_paginator_when_one_site=False,
            disable_search_btn=True,
            **self._base_init_kwargs
        )
        return await super().start(ctx)


    async def _update_position(self, interaction: ComponentInteraction | None = None, detailed=False):
        """
        replaces embed page first with a more detailed one, before sending the message
        """
        self._current_has_prequel = False
        self._current_has_sequel = False
        await self._load_details(detailed=detailed)
        if detailed:
            self._detailed = True
        await super()._update_position(interaction)
        self._detailed = False


    def _fuzzy_sort_results(self, compare_name: str):
        """fuzzy sort the anime result titles of  `self._results` by given name"""
        close_matches = []
        for anime in self._results.copy():
            # get all titles
            titles = [anime["node"]["title"]]
            if (alt_titles := anime["node"]["alternative_titles"]) and isinstance(alt_titles, dict):
                for value in alt_titles.values():
                    if isinstance(value, list):
                        titles.extend(value)
                    else:
                        titles.append(value)
                        
            max_ratio = max([fuzz.ratio(title.lower(), compare_name) for title in titles])
            anime["fuzz_ratio"] = max_ratio
            if anime["fuzz_ratio"] >= 80:
                self._results.remove(anime)
                close_matches.append(anime)
        close_matches.sort(key=lambda anime: anime["fuzz_ratio"], reverse=True)
        self._results = [*close_matches, *self._results]


    async def _search_anime(self, search: str | None, results: List[Dict[str, Dict[str, int]]] | None = None) -> List[hikari.Embed]:
        """
        Search <`search`> anime, and set results to `self._results`. These have less information
        
        Args:
        ----
        search : str | None
            the name of the anime to get results from.
            None if <`results`> are given
        results : List[Dict[str, Dict[str, int]]] | None
            results, if already given.
            Must use following structure:
                [
                    {"node": 
                        {"id": int}
                    }
                ]
        """
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
                    # add search result if name is similar with user given name
                    animes.append(anime)
            # if no results, start more complex search
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
                        .set_footer(text=f"page {i+1}/{total}")
                    )
                )
            return embeds
        if results:
            self._results = results
            # create embed spaceholders
            embeds = [Embed(title="spaceholder") for _ in range(len(results))]
        else:
            results = await MyAnimeList.search_anime(query=search)
            # store result list
            self._results = results["data"]
            # sort the list by comparing with given name
            self._fuzzy_sort_results(search)
            # build embeds out of results
            embeds = build_embeds(search, self._results)
        if not embeds:
            return [hikari.Embed(title="Nothing found")]
        return embeds


    async def _fetch_current_anime(self) -> Anime:
        """
        Fetches or returns already fetched anime

        Given MAL Dict (stored in `self._results`) needs following structure:
        [
            {"node": 
                {"id": int}
            }
        ]
        """
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

        self._current_has_prequel = False
        self._current_has_sequel = False
        
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
        embed: hikari.Embed = (
            hikari.Embed()
            .add_field("Type", anime.type_, inline=True)
            .add_field("Score", f"||{anime.score}/10||", inline=True)
            .add_field("Episodes", f"{Human.plural_('episode', anime.episodes)}", inline=True)
            .add_field("Rank", f"{anime.rank} ", inline=True)
            .add_field("Popularity", popularity, inline=True)
            .add_field("Age", f"{anime.rating}", inline=True)
            .add_field("Duration", f"{anime.duration / 60:.1f} min per episode", inline=True)
            .set_image(anime.image_url)
        )

        # add genres
        if anime.genres:
            embed.add_field(
                "Genres",
                ", ".join(anime.genres),
                inline=True,
            )
        
        # add dub status
        embed.add_field(
            "Dub Status", 
            f"[Is it dubbed?]({anime.is_it_dubbed})", 
            inline=True
        )

        # add studios
        if anime.studios and detailed:
            embed.add_field(
                "Studios", 
                ", ".join(anime.studios),
                inline=True
            )

        # add synonyms
        if anime.title_synonyms:
            synonyms = ",\n".join(anime.title_synonyms)
            embed.add_field(
                "Synonyms", 
                synonyms,
                inline=len(synonyms) < 80,
            )
        
        # add airing time
        embed.add_field(
            "Airing Time 📅",
            anime.airing_str,
            inline=True
        )

        # adding additional information
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
        fmt_prequel = "⏪ Prequel"
        fmt_sequel = "Sequel ⏩"
        for relation_type, relations in anime.related.items():
            # related contains dict with mapping from relation_type to list of relations
            # one relation is a node with keys "mal_id", "title", "type", "mal_url"..
            related_str =""
            fmt_relation = ""
            if relation_type == "prequel":
                fmt_relation = fmt_prequel
                self._current_has_prequel = True
            elif relation_type == "sequel":
                fmt_relation = fmt_sequel
                self._current_has_sequel = True
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

        if self._current_has_prequel and self._current_has_sequel and embed.fields:
            to_move: List[hikari.EmbedField] = []
            for field in embed.fields:
                if field.name in [fmt_prequel, fmt_sequel]:
                    to_move.append(field)
            # change prequel and sequel if reversed
            if to_move[0].name == fmt_sequel:
                to_move.insert(0, to_move.pop(-1))
            # remove field from somewhere in the embed
            [embed._fields.remove(item) for item in to_move]
            # move them in the right order to the end
            [embed._fields.append(item) for item in to_move]


        
        if anime.background and detailed:
            embed.add_field("Background", Human.short_text(anime.background, 200))

        if (len_openings := len(anime.opening_themes)) > self._max_openings:
            embed.add_field("Opening themes", ("\n".join(anime.opening_themes[:3]) + f"\n... ({len_openings-3})"), inline=False)
        elif len_openings == 0:
            pass
        else:
            embed.add_field("Opening themes", "\n".join(anime.opening_themes))

        if detailed:
            embed.add_field("Completion rate", f"{anime.completion_rate}", inline=True)

        # add endings if not too much
        if (len_endings := len(anime.ending_themes)) > self._max_endings:
            embed.add_field("Ending themes", ("\n".join(anime.ending_themes[:3]) + f"\n... ({len_endings-3})"), inline=False)
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
        embed.set_footer(text=f"page {self._position+1}/{len(self.pages)} | {anime.title}")

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

    @property
    def has_prequel(self) -> bool:
        """wether or not the current anime has a prequel"""
        return self._current_has_prequel
    
    @property
    def has_sequel(self) -> bool:
        """wether or not the current anime has a sequel"""
        return self._current_has_sequel

    @property
    def prequel_id(self) -> int:
        try:
            anime = self._results[self._position].get("anime")
            if not isinstance(anime, Anime):
                raise RuntimeError(f"It was supposed, that anime is an instance of `Anime`")
            nodes = anime.related["prequel"]
            anime_url = [node["url"] for node in nodes if node["relation_type"] == "prequel"][0]
            regex = f"anime\/([0-9]+)$"
            return int((re.findall(regex, anime_url))[0])
        except Exception as e:
            log.debug(f"can't find prequel id for anime {anime or None}")
            raise e

    @property
    def sequel_id(self) -> int:
        try:
            anime = self._results[self._position].get("anime")
            if not isinstance(anime, Anime):
                raise RuntimeError(f"It was supposed, that anime is an instance of `Anime`")
            nodes = anime.related["sequel"]
            anime_url = [node["url"] for node in nodes if node["relation_type"] == "sequel"][0]
            regex = f"anime\/([0-9]+)$"
            return int((re.findall(regex, anime_url))[0])
        except Exception as e:
            log.debug(f"can't find sequel id for anime {anime or None}")
            raise e

    @property
    def has_too_many_endings(self) -> bool:
        return len(self.current_anime.ending_themes) > self._max_endings

    @property
    def has_too_many_openings(self) -> bool:
        return len(self.current_anime.opening_themes) > self._max_openings

    @property
    def current_anime(self) -> Anime:
        """
        Raises:
        ------- 
        RuntimeError :
            if self._results[self._position] has no key "anime" aka the anime wasn't fetched
        """
        anime = self._results[self._position].get("anime")
        if not isinstance(anime, Anime):
            raise RuntimeError(f"It was supposed, that anime is an instance of `Anime`\nMaybe called before site was updated/fetched?")
        return anime

    def _set_anime_id_as_next_item(self, anime_id: int):
        self.pages.insert(self._position+1, Embed(title=f"Anime [{anime_id}]"))
        self._results.insert(self._position+1, {"node": {"id": anime_id}})
        

class AnimeMatch(TypedDict):
    rank: int
    rank_suffix: str
    name: str
    score: float


class AnimeCornerPaginator(Paginator):
    anime_matches: List[AnimeMatch]
    submission: asyncpraw.models.Submission
    anime_paginators: List[AnimePaginator | None]
    title: str
    active_anime_paginator: AnimePaginator | None = None

    def __init__(
        self,
        **kwargs
    ):
        self.anime_matches = []
        self.submission: asyncpraw.models.Submission | None = None
        self.anime_paginators = []
        self.title = ""
        self.active_anime_paginator = None

        # re-init in start - just leave it
        super().__init__(
            page_s=["None"], 
            timeout=60*2,
        )
        

    async def start(
        self, 
        ctx: Context, 
        submission: asyncpraw.models.Submission,
        title: str,
    ) -> hikari.Message:
        """
        entry point for paginator

        Args:
        ----
        ctx : lightbulb.Context
            The context to use to send the initial message
        anime_name : str | None
            the name of the anime which should be searched
        results : List[Dict[str, Dict[str, int]]] | None
            results, if already given.
            Must use following structure:
                [
                    {"node": 
                        {"id": int}
                    }
                ]
        """
        self.ctx = ctx

        
        self.anime_paginators = []
        self.submission = submission
        self.title = title
        self._pages = [self.default_embed]

        self._position = 0
        super().__init__(
            page_s=self._pages, 
            timeout=60*4, 
            disable_paginator_when_one_site=False,
            disable_search_btn=True,
            number_button_navigation=True,
        )
        task = asyncio.create_task(self.fetch_matches())
        return await super().start(ctx)
    
    async def fetch_matches(self):
        """
        fetches the matches and updates this paginator
        """
        try:
            anime_corner = AnimeCornerAPI()
            self.anime_matches = (await anime_corner.fetch_ranking(self.anime_corner_url))[:10]
            self._pages = [self.default_embed for _ in range(len(self.anime_matches))]
            self.anime_paginators = [None for _ in range(len(self.anime_matches))]
            # update components
            await super()._update_position()
        except Exception as e:
            traceback.print_exc()

    @property
    def anime_corner_url(self) -> str:
        # https://animecorner.me/spring-2023-anime-rankings-week-12/
        # Top 10 Anime of the Week #01 - Summer 2023 (Anime Corner)
        REGEX = r"^Top 10 Anime of the Week #(?P<week_number>\d+) - (?P<season>\w+) (?P<year>\d+)(?: \(Anime Corner\))?$"
        match_ = re.match(REGEX, self.title)
        if not match_:
            raise RuntimeError(f"Couldn't match title {self.title} with regex {REGEX}")
        week_number = int(match_.group("week_number"))
        season = match_.group("season").lower()
        year = match_.group("year")
        return f"https://animecorner.me/{season}-{year}-anime-rankings-week-{week_number}/"

    async def _update_position(self, interaction: ComponentInteraction | None = None, detailed=False):
        """
        replaces embed page first with a more detailed one, before sending the message
        """
        await super()._update_position()
        # this starts the sub-anime paginator; this paginator needs to be updated first
        await self.load_page()
        

    @property
    def default_embed(self) -> Embed:
        season_to_color_map = {
            "winter": "#32acd5",
            "spring": "#eb2b48",
            "summer": "#ffe9cc",
        }
        # get color for season from submission title
        color = "32acd5"
        for season, c in season_to_color_map.items():
            if season in self.submission.title.lower():
                color = c
                break

        return (
            Embed(title=self.title, color=color)
            .set_image(self.submission.url)
        )

    async def load_page(self):
        """
        starts the anime paginator of current index
        """
        old_pag = self.active_anime_paginator
        
        if self.anime_paginators[self._position] is None:
            self.anime_paginators[self._position] = await self._load_page()
        self.active_anime_paginator = self.anime_paginators[self._position]

        if old_pag is not None and not old_pag == self.active_anime_paginator and not old_pag._stopped:
            await old_pag.delete_presence()
        
        anime_match = self.anime_matches[self._position]
        task = asyncio.create_task(self.active_anime_paginator.start(self.ctx, anime_match["name"]))
        return self.active_anime_paginator
    
    async def _load_page(self) -> Paginator:
        
        anime_pag = AnimePaginator()
        #self.ctx._update = True
        #await self.ctx.defer()
        return anime_pag
    


class AnimeCornerPaginator2(AnimePaginator):
    anime_matches: List[AnimeMatch]
    submission: asyncpraw.models.Submission
    anime_paginators: List[AnimePaginator | None]
    title: str
    active_anime_paginator: AnimePaginator | None = None
    _genre_table: str
    _animes: List[Anime]

    def __init__(
        self,
        **kwargs
    ):
        self.anime_matches = []
        self.submission: asyncpraw.models.Submission = None
        self.anime_paginators = []
        self.title = ""
        self.active_anime_paginator = None
        self._loaded_results = [{} for _ in range(11)]
        self._results = []
        self._anime_corner_task: asyncio.Task | None = None
        self._genre_table = ""

        # re-init in start - just leave it
        super().__init__(
            page_s=["None"], 
            timeout=60*4, 
            disable_paginator_when_one_site=False,
            disable_search_btn=True,
            number_button_navigation=True,
        )
        

    async def start(
        self, 
        ctx: Context, 
        submission: asyncpraw.models.Submission,
        title: str,
    ) -> hikari.Message:
        """
        entry point for paginator

        Args:
        ----
        ctx : lightbulb.Context
            The context to use to send the initial message
        anime_name : str | None
            the name of the anime which should be searched
        results : List[Dict[str, Dict[str, int]]] | None
            results, if already given.
            Must use following structure:
                [
                    {"node": 
                        {"id": int}
                    }
                ]
        """
        self.ctx = ctx
        self.anime_paginators = []
        self.submission: asyncpraw.models.Submission = submission
        self.title = title
        self._animes: List[Anime] = []
        self._pages = [self.default_embed for _ in range(11)]
        super(AnimePaginator, self).__init__(
            page_s=self._pages,
            timeout=60*14, 
            disable_paginator_when_one_site=False,
            disable_search_btn=True,
            number_button_navigation=True,
            default_page_index=-1,
        )
        # start fetching Anime Corner Matches
        self._anime_corner_task = asyncio.create_task(self.fetch_matches())
        # create and add callback to set footer
        def _anime_corner_callback():
            self._pages[-1] = self.default_embed
            self._pages[-1].set_footer(
                f"page {len(self._pages)}/{len(self._pages)} | {self.title}"
            )
            asyncio.create_task(self._update_position())
        self._anime_corner_task.add_done_callback(
            lambda _: _anime_corner_callback()
        )
        await self._anime_corner_task
        return await super(AnimePaginator, self).start(ctx)
    
    
    async def _make_genre_percentage_table(self) -> str:
        """
        Creates a table with genre percentages, limited to top 10 genres and sorted.
        """
        if not self._animes:
            raise RuntimeError("Anime not fetched yet to ._animes")
        
        genres = {}
        for anime in self._animes:
            for genre in anime.genres:
                genres[genre] = genres.get(genre, 0) + 1
        
        total = len(self._animes)
        
        # Sort genres by count and limit to top 16
        sorted_genres = sorted(genres.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Calculate percentages
        genre_percentages = [(genre, count, (count / total) * 100) for genre, count in sorted_genres]
        
        table = tabulate(
            genre_percentages,
            headers=["Genre", "Amount", "Percentage", ""],
            tablefmt="rounded_outline",
            floatfmt=".0f"
        )
        self._genre_table = f"```{table}```"
        return self._genre_table
    
    async def fetch_matches(self):
        """
        fetches the matches and updates this paginator
        """
        try:
            anime_corner = AnimeCornerAPI()
            self.anime_matches: List[PartialAnimeMatch] = (await anime_corner.fetch_ranking(self.anime_corner_url))[:10]
            animes = await AnimeCornerView.fetch_anime_matches(self.anime_matches)
            self._animes = animes
            await self._make_genre_percentage_table()
        except Exception as e:
            traceback.print_exc()

    @property
    def anime_corner_url(self) -> str:
        # https://animecorner.me/spring-2023-anime-rankings-week-12/
        # Top 10 Anime of the Week #01 - Summer 2023 (Anime Corner)
        REGEX = r"^Top 10 Anime of the Week #(?P<week_number>\d+) - (?P<season>\w+) (?P<year>\d+)(?: \(Anime Corner\))?$"
        match_ = re.match(REGEX, self.title)
        if not match_:
            raise RuntimeError(f"Couldn't match title {self.title} with regex {REGEX}")
        week_number = int(match_.group("week_number"))
        season = match_.group("season").lower()
        year = match_.group("year")
        return f"https://animecorner.me/{season}-{year}-anime-rankings-week-{week_number}/"

    async def _update_position(self, interaction: ComponentInteraction | None = None, detailed=False):
        """
        replaces embed page first with a more detailed one, before sending the message
        """
        
        # this starts the sub-anime paginator; this paginator needs to be updated first
        if self._position != len(self._pages) - 1:
            if not self._anime_corner_task.done():
                self.ctx._update = True
                await self.ctx.defer(update=True)
                await self._anime_corner_task
            if self._pages[self._position].title == self.default_embed.title:
                # anime is not loaded yet - defer interaction
                search = self.anime_matches[self._position]["name"]
                page = deepcopy(self._pages[self._old_position])
                page.set_footer(f"Loading Anime {search}...")
                components = self.build_default_components(self._position)
                # set current button to red
                for i, row in enumerate(components):
                    for j, component in enumerate(row.components):
                        # current page is marked as stop in case of pressing again to stop
                        if component.custom_id == f"stop":
                            component.set_is_disabled(True)
                await self.send(page, components=components)
                results = await MyAnimeList.search_anime(query=search)
                # store result list
                self._results = results["data"]
                # sort the list by comparing with given name
                self._fuzzy_sort_results(search)
                await self._load_details()
        await super(AnimePaginator, self)._update_position()
        

    @property
    def default_embed(self) -> Embed:
        season_to_color_map = {
            "winter": "#32acd5",
            "spring": "#eb2b48",
            "summer": "#ffe9cc",
            "fall": "#FF974F",
        }
        # get color for season from submission title
        color = "32acd5"
        for season, c in season_to_color_map.items():
            if season in self.submission.title.lower():
                color = c
                break
        embed = Embed(title=self.title, color=color)
        embed.add_field("Next poll:", "[polls - AnimeCorner](https://polls.animecorner.me/)", inline=True)
        embed.add_field("Article:", f"[here]({self.anime_corner_url})", inline=True)
        embed.add_field("Reddit Post:", f"[here](https://reddit.com{self.submission.permalink})", inline=True)
        embed.add_field("Genre Table", self._genre_table or "?", inline=False)
        embed.set_image(self.submission.url)
        if not self.anime_matches:
            embed.set_footer(text="Loading Animes...")
        return embed

    async def load_page(self):
        """
        starts the anime paginator of current index
        """
        old_pag = self.active_anime_paginator
        
        if self.anime_paginators[self._position] is None:
            self.anime_paginators[self._position] = await self._load_page()
        self.active_anime_paginator = self.anime_paginators[self._position]
        if old_pag is not None and not old_pag == self.active_anime_paginator and not old_pag._stopped:
            await old_pag.delete_presence()
        
        anime_match = self.anime_matches[self._position]
        task = asyncio.create_task(self.active_anime_paginator.start(self.ctx, anime_match["name"]))
        return self.active_anime_paginator
    
    async def _load_page(self) -> Paginator:
        
        anime_pag = AnimePaginator()
        #self.ctx._update = True
        #await self.ctx.defer()
        return anime_pag
    
    async def _fetch_current_anime(self) -> Anime:
        """
        Fetches or returns already fetched anime

        Given MAL Dict (stored in `self._results`) needs following structure:
        [
            {"node": 
                {"id": int}
            }
        ]

        Override:
        --------
        always fetch first result from `self._results`
        """
        # fetch anime if not done yet
        anime: Anime
        if not (anime := self._loaded_results[self._position].get("anime")):
            mal_id = self._results[0]["node"]["id"]
            anime = await MyAnimeList.fetch_anime_by_id(mal_id)
            self._loaded_results[self._position]["anime"] = anime
        log.debug(f"fetched anime: {anime}")
        return anime

    def build_default_components(self, position=None) -> Optional[List[Optional[MessageActionRowBuilder]]]:
        components = super(AnimePaginator, self).build_default_components(position)
        return components





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