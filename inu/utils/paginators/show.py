import asyncio
from typing import *
from enum import Enum
from datetime import date
from statistics import median

import hikari
from hikari import ButtonStyle, ComponentInteraction, Embed
from hikari.impl import MessageActionRowBuilder
from tmdb import route
from tabulate import tabulate
from fuzzywuzzy import fuzz

from .base import Paginator, listener

from core import getLogger, InuContext, ConfigProxy, ConfigType, BotResponseError, get_context
from utils import Human, crumble

log = getLogger(__name__)



config = ConfigProxy(ConfigType.YAML)
size = "/original"
base_url = f"https://image.tmdb.org/t/p{size}"
base = route.Base()
base.key = config.tmdb.SECRET

class SortBy:
    @staticmethod
    def by_score(embeds: List[Embed]) -> List[Embed]:
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


    def build_default_components(self, position=None) -> List[MessageActionRowBuilder]:
        components = super().build_default_components(position)
        components.append(
            MessageActionRowBuilder()
            .add_button(ButtonStyle.SECONDARY, "tv_show_seasons").set_label("Seasons").add_to_container()
        )
        return components


    async def start(self, ctx: InuContext, show_name: str) -> hikari.Message:
        """
        entry point for paginator

        Args:
        ----
        ctx : InuContext
            The context to use to send the initial message
        show_name : str
            the name of the show
        
        """
        self.ctx = ctx
        self._position = 0
        self._pages = await self._search_show(show_name)
        await self._load_details()
        super().__init__(
            page_s=self._pages, 
            timeout=4*60, 
            disable_paginator_when_one_site=False,
            disable_search_btn=True,
            number_button_navigation=False,
            **self._base_init_kwargs
        )
        return await super().start(ctx)


    @listener(hikari.InteractionCreateEvent)
    async def on_interaction(self, event: hikari.InteractionCreateEvent):
        if not self.interaction_pred(event):
            return
        i = event.interaction
        if i.custom_id == "tv_show_seasons":
            pag = ShowSeasonPaginator(
                page_s=["none"], 
                timeout=4*60, 
                first_message_kwargs={
                    "content": f"{self._results[self._position]['name']} season overview"
                },
                number_button_navigation=True,
            )
            ctx = get_context(event)
            seasons: Optional[List[Dict[str, str | int]]]= self._results[self._position].get("seasons")
            if not seasons:
                return await ctx.respond(
                    "No seasons to show", ephemeral=True
                )
            return await pag.start(
                ctx, 
                tv_show_id=self._results[self._position]["id"], 
                season_response=seasons
            )

            

    async def _search_show(self, search: str) -> List[hikari.Embed]:
        """
        Search a tv show. Returned Embeds are apceholders. Acutall pages will be
        loaded lazy
        
        Args:
        ----
        search : str
            the name of the tv show to get results from
        """
        show_route = route.Show()
        show_json = await show_route.search(search)
        self._results = show_json["results"]
        await show_route.session.close()
        embeds = [Embed(description="spaceholder") for _ in range(len(self._results))]
        if len(embeds) == 0:
            raise BotResponseError("Seems like your given TV show doesn't exist", ephemeral=True)
        return embeds


    async def _load_details(self) -> None:
        """
        loads details of current tv show into self._page
        """
        if not self._pages[self._position].description == "spaceholder":
            return
        
        try:
            show_route = route.Show()
            details = await show_route.details(self._results[self._position]["id"])
        except IndexError:
            raise BotResponseError("Seems like your given TV show doesn't exist", ephemeral=True)
        finally:
            await show_route.session.close()
        
        # otherwise not accessible for season button
        self._results[self._position] = details
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
        embed.add_field("Score", f"{details['vote_average']:.1f}/10", inline=True)
        
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
            # create season overview
            data: Dict[str, List[str]] = {
                "Episodes": [],
                "Date": [],
                "Name": []
            }
            for season in seasons:
                try:
                    d = date.fromisoformat(season.get("air_date", "2000-00-00"))
                    aired = f"{d.month:02}/{d.year}"
                except:
                    aired = "--/----"
                data["Episodes"].append(f"{season.get('episode_count', 0)}")
                data["Name"].append(Human.short_text(season.get("name", "Unnamed"), 34))
                data["Date"].append(aired)
            season_overview = tabulate(data, tablefmt="rounded_outline", headers=["Eps", "Date", "Name"])
            for i, field in enumerate(crumble(season_overview, 1000)):
                if i == 0:
                    name = "Season Overview"
                else:
                    name = "..."
                embed.add_field(name, f"```\n{field}```", inline=False)

        embed.set_image(f"{base_url}{details['poster_path']}")

        
        embed._fields = [f for f in embed.fields if f.value and f.name]
        self._pages[self._position] = embed


    async def _update_position(self, interaction: ComponentInteraction | None = None,):
        """
        replaces embed page first with a more detailed one, before sending the message
        """
        await self._load_details()
        await super()._update_position(interaction)



class ShowSeasonPaginator(Paginator):
    _results: List[Dict[str, Any]]  # bare season info
    _tv_show_id: int

    async def start(self, ctx: InuContext, tv_show_id: int, season_response: List[Dict[str, Any]], **kwargs):
        """
        Args:
        `ctx : InuContext`
            the context
        `tv_show_id : int`
            id of tv show
        `season_resposne : List[Dict[str, Any]]`
            the part of the json resposne containing the season list
        """
        self._tv_show_id = tv_show_id
        self._results = season_response
        
        self.ctx = ctx
        self._position = 0
        # if first season name is "Specials", move it to the end
        if self._results[0]["name"] == "Specials":
            self._results.append(self._results.pop(0))
        self._pages = [Embed(description="spaceholder") for _ in range(len(self._results))]
        await self._load_details()
        if not self._pages:
            return

        return await super().start(ctx)


    async def _load_details(self) -> None:
        """
        fetches season information and updates current self._page
        """
        try:
            if not self._pages[self._position].description == "spaceholder":
                return
            show_route = route.Season()
            details = await show_route.details(self._tv_show_id, self._results[self._position]["season_number"])
            await show_route.session.close()
        except IndexError:
            return await self.ctx.respond("Seems like there is no season preview for this TV show", ephemeral=True)
            
        embed = Embed(description="")
        def add_key_to_field(name: str, key: str, inline=True, default=None):
            if (value := details.get(key, "None")):
                embed.add_field(name, str(value), inline=inline)
        
        embed.title = details["name"]
        if (overview := details.get("overview")):
            embed.description = overview

        min_score_ep = None
        max_score_ep = None
        if (episodes := details.get("episodes")):
            min_score_ep = min(episodes, key=lambda e: e["vote_average"])
            max_score_ep = max(episodes, key=lambda e: e["vote_average"])


        # add embed field for max score episode
        if max_score_ep:
            embed.add_field(
                "🔺 Highest rated EP", 
                f"{max_score_ep['vote_average']:.1f}/10", 
                inline=True
            )
        # add embed field for average score
        avg_score = median(
            [e["vote_average"] for e in details.get("episodes", [])] or [0]
        )
        embed.add_field("🔹 Score", f"{avg_score:.1f}/10", inline=True)

        # add embed field for min score episode
        if min_score_ep:
            embed.add_field(
                "🔻Lowest rated EP", 
                f"{min_score_ep['vote_average']:.1f}/10", 
                inline=True
            )


        add_key_to_field("Season number", "season_number", inline=True)
        # Add Air date as MM/YYYY
        if (air_date := details.get("air_date")):
            try:
                d = date.fromisoformat(air_date)
                aired = f"{d.month:02}/{d.year}"
            except:
                aired = "--/----"
            embed.add_field("Air date", aired, inline=True)
        embed.add_field("Episodes", str(len(details.get("episodes", []))), inline=True)

        name_min_max_ep = ""
        # make both EPs equaly long
        if min_score_ep and max_score_ep:
            # get max length of both names
            max_len = max(len(min_score_ep.get("name", "")), len(max_score_ep.get("name", ""))) + 8
            log.debug(f"max_len: {max_len}")
        if min_score_ep:
            str_ = f"{min_score_ep.get('name', '')} (EP {min_score_ep['episode_number']})"
            # center text in the middle
            name_min_max_ep += f"Lowest rated EP name: ||`{str_:^{max_len}}`||\n"
        if max_score_ep:
            str_ = f"{max_score_ep.get('name', '')} (EP {max_score_ep['episode_number']})"
            name_min_max_ep += f"Highest rated EP name: ||`{str_:^{max_len}}`||\n"
        if name_min_max_ep:
            embed.add_field("Episode details", name_min_max_ep, inline=False)
        
        embed.set_image(f"{base_url}{details['poster_path']}")
        embed._fields = [f for f in embed.fields if f.value and f.name]
        self._pages[self._position] = embed

    async def _update_position(self, interaction: ComponentInteraction | None = None,):
        """
        replaces the current season page with the rest response. This works lazy
        """
        await self._load_details()
        await super()._update_position(interaction)



class MoviePaginator(Paginator):
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


    async def start(self, ctx: InuContext, movie_name: str) -> hikari.Message:
        """
        entry point for paginator

        Args:
        ----
        ctx : InuContext
            The context to use to send the initial message
        movie_name : str
            the name of the movie
        
        """
        self.ctx = ctx
        self._position = 0
        self._pages = await self._search_movie(movie_name)
        await self._load_details()
        super().__init__(
            page_s=self._pages,
            timeout=4*60,
            disable_paginator_when_one_site=False,
            disable_search_btn=True,
            number_button_navigation=False,
            **self._base_init_kwargs
        )
        return await super().start(ctx)


    async def _search_movie(self, search: str) -> List[hikari.Embed]:
        """
        Search for a movie. Returned Embeds are placeholders. Actual pages will be
        loaded lazily
        
        Args:
        ----
        search : str
            the name of the movie to get results from
        """
        movie_route = route.Movie()
        movie_json = await movie_route.search(search)
        self._results = movie_json["results"]
        await movie_route.session.close()
        self._results.sort(key=lambda x: fuzz.partial_token_set_ratio(search, x["title"]), reverse=True)

        embeds = [Embed(description="spaceholder") for _ in range(len(self._results))]
        if len(embeds) == 0:
            raise BotResponseError("Seems like your given movie doesn't exist", ephemeral=True)
        return embeds


    async def _load_details(self) -> None:
        """
        Loads details of current movie into self._page
        """
        if not self._pages[self._position].description == "spaceholder":
            return

        try:
            movie_route = route.Movie()
            details = await movie_route.details(self._results[self._position]["id"])
        except IndexError:
            raise BotResponseError("Seems like your given movie doesn't exist", ephemeral=True)
        finally:
            await movie_route.session.close()

        # otherwise not accessible for season button
        self._results[self._position] = details
        embed = Embed(description="")
        
        def add_key_to_field(name: str, key: str, inline=True, default=None):
            if (value := details.get(key, "None")):
                embed.add_field(name, str(value), inline=inline)

        def join_list_dict_keys(key: str):
            value = details.get(key, [])
            return ", ".join([n["name"] for n in value if n.get("name")])
        
        embed.title = details["title"]
        embed.set_footer(details["title"])
        if (tagline := details.get("tagline")):
            embed.description += f"_{tagline}_\n\n"
        embed.description += Human.short_text(details["overview"], 1950)

        # direction in emoji:  
        embed.add_field("Popularity", f'{round(details["popularity"])}', inline=True)
        embed.add_field("Score", f"{details['vote_average']:.1f}/10", inline=True)
        add_key_to_field("⏱️ Runtime", "runtime")
        embed.add_field("💰 Budget", f"${details['budget']:,}", inline=True)
        embed.add_field("🎬 Genres", join_list_dict_keys("genres"), inline=True)
        embed.add_field("💸 Revenue", f"${details['revenue']:,}", inline=True)
        # revenue / budget
        if details["budget"] > 0 and details["revenue"] > 0:
            embed.add_field(
                "Profit", 
                f"{details['revenue'] / details['budget']:.1f}x", 
                inline=True
            )

        # add release date in MM/YYYY format from iso format
        if (release_date := details.get("release_date")):
            try:
                d = date.fromisoformat(release_date)
                aired = f"{d.month:02}/{d.year}"
            except:
                aired = "--/----"
            embed.add_field("📅 Release date", aired, inline=True)
        add_key_to_field("Status", "status")
        add_key_to_field("Original Language", "original_language")
        add_key_to_field("Original Title", "original_title")
        add_key_to_field("Vote Count", "vote_count")
        if (belongs_to_collection := details.get("belongs_to_collection")):
            embed.add_field("Belongs to", belongs_to_collection["name"], inline=False)
        embed.add_field("Produced in", join_list_dict_keys("production_countries"), inline=False)
        embed.add_field("Produced from", join_list_dict_keys("production_companies"), inline=False)
        add_key_to_field("Homepage", "homepage", inline=False)


        if (video := details.get("videos")) and (results := video.get("results", [])):
            embed.add_field("Trailer", f"[Link]({route.Movie().youtube_link(results[0]['key'])})", inline=False)

        if (poster_path := details.get("poster_path")):
            embed.set_image(f"{base_url}{poster_path}")
        
        embed._fields = [f for f in embed._fields if f.value and f.name]

        self._pages[self._position] = embed

    async def _update_position(self, interaction: ComponentInteraction | None = None,):
        """
        replaces the current season page with the rest response. This works lazy
        """
        await self._load_details()
        await super()._update_position(interaction)

