import asyncio
from typing import *
from enum import Enum
from pprint import pprint
import random
import traceback
from pprint import pformat
import re
from copy import deepcopy, copy
from datetime import date, datetime

import hikari
from hikari import ButtonStyle, ComponentInteraction, Embed, ResponseType
from hikari.impl import MessageActionRowBuilder
import lightbulb
from numpy import longdouble, sort
from pyparsing import CloseMatch
from tmdb import route, schema

from .base import PaginatorReadyEvent, Paginator, listener
from jikanpy import AioJikan
from fuzzywuzzy import fuzz

from core import getLogger, InuContext, ConfigProxy, ConfigType
from utils import Human, Colors, MyAnimeList, Anime

log = getLogger(__name__)



config = ConfigProxy(ConfigType.YAML)
size = "/original"
base_url = f"https://image.tmdb.org/t/p{size}"
base = route.Base()
base.key = config.tmdb.SECRET

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


class ShowPaginator(Paginator):
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


    async def start(self, ctx: InuContext, show_name: str) -> hikari.Message:
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
        self._position = 0
        self._pages = await self._search_show(show_name)
        await self._load_details()
        super().__init__(
            page_s=self._pages, 
            timeout=60*4, 
            disable_paginator_when_one_site=False,
            disable_search_btn=True,
            **self._base_init_kwargs
        )
        return await super().start(ctx)

    # def _fuzzy_sort_results(self, compare_name: str):
    #     """fuzzy sort the anime result titles of  `self._results` by given name"""
    #     close_matches = []
    #     for anime in self._results.copy():
    #         anime["fuzz_ratio"] = fuzz.ratio(anime["node"]["title"].lower(), compare_name.lower())
    #         if anime["fuzz_ratio"] >= 80:
    #             self._results.remove(anime)
    #             close_matches.append(anime)
    #     close_matches.sort(key=lambda anime: anime["fuzz_ratio"], reverse=True)
    #     self._results = [*close_matches, *self._results]


    async def _search_show(self, search: str) -> List[hikari.Embed]:
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
        show_route = route.Show()
        show_json = await show_route.search(search)
        await show_route.session.close()
        embeds = [Embed(description="spaceholder") for _ in range(len(show_json) -1)]
        self._results = show_json["results"]
        return embeds

    async def _load_details(self) -> None:
        """

        """
        if not self._pages[self._position].description == "spaceholder":
            return
        show_route = route.Show()
        details = await show_route.details(self._results[self._position]["id"])
        await show_route.session.close()
        
        embed = Embed(description="")
        def add_key_to_field(name: str, key: str, inline=True):
            if (value := details.get(key, "None")):
                embed.add_field(name, str(value), inline=inline)
        
        embed.title = details["name"]
        embed.set_footer(details["name"])
        if (tagline := details.get("tagline")):
            embed.description += f"_{tagline}_\n"  # type: ignore
        embed.description = Human.short_text(details["overview"], 1950)
        embed.add_field("Popularity", f'{round(details["popularity"])}', inline=True)
        embed.add_field("Score", f"{details['vote_average']:.2}/10", inline=True)
        
        embed.add_field("Episodes", Human.plural_("episode", details["number_of_episodes"], True), inline=True)
        embed.add_field("Seasons", Human.plural_("season", details["number_of_seasons"], True), inline=True)
        embed.add_field("Genres", ", ".join([n["name"] for n in details["genres"] if n.get("name")]), inline=True)
        add_key_to_field("Votes", "vote_count")
        add_key_to_field("Original Language", "original_language")
        add_key_to_field("Last air date", "last_air_date")
        embed.add_field("In production", Human.bool_(details["in_production"]), inline=True)
        embed.add_field("Streaming Services", ", ".join([n["name"] for n in details["networks"] if n.get("name")]), inline=True)
        embed.add_field("Producers", ", ".join([n["name"] for n in details["production_companies"] if n.get("name")]), inline=True)
        if (episode_runtime := details.get("episode_run_time")):
            embed.add_field("Duration", ", ".join(f"{e} min/Episode" for e in episode_runtime))
        
        if (seasons := details.get("seasons")):
            season_overview = f"{'Season':<14}{'Episodes':<12}Date\n" # name, episode number, date
            for season in seasons:
                try:
                    d = date.fromisoformat(season.get("air_date", "2000-00-00"))
                    aired = f"{d.month}/{d.year}"
                except:
                    aired = "/"
                season_overview += f'{season.get("name", "None"):<14}{season.get("episode_count", "None"):<12}{aired}\n'
            embed.add_field("Season Overview", f"```\n{season_overview}```", inline=False)

        embed.set_image(f"{base_url}{details['poster_path']}")

        
        embed._fields = [f for f in embed.fields if f.value and f.name]
        self._pages[self._position] = embed

    async def _update_position(self, interaction: ComponentInteraction | None = None,):
        """
        replaces embed page first with a more detailed one, before sending the message
        """
        await self._load_details()
        await super()._update_position(interaction)

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
