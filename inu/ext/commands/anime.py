import asyncio
from datetime import datetime, timedelta
from typing import *
import hikari
import lightbulb
import traceback

from cachetools import TTLCache
from fuzzywuzzy import fuzz
from hikari import (
    Embed,
    ResponseType,
    TextInputStyle,
    Permissions,
    ButtonStyle,
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import Context, Loader, Group, SubGroup, SlashCommand, invoke
from lightbulb.prefab import sliding_window

from inu.utils import (
    Human,
    Paginator,
    AnimePaginator,
    AnimeCharacterPaginator,
    AnimeCornerHistoryPaginator,
    MangaPaginator,
    check_website,
    MAGIC_ERROR_MONSTER,
)
from inu.utils.db import AnimeCornerHistoryManager
from inu.utils.paginators.anime_corner_history import parse_season_arg
from inu.core import BotResponseError, getLogger, get_context, InuContext

log = getLogger(__name__)
loader = lightbulb.Loader()

# Discord caps a single slash-command option at 25 choices. Slot 0 is the
# synthetic "current" entry; the remaining 24 are the most recent
# (season, year) pairs the history table actually has data for.
# AnimeCorner runs weekly, so a short TTL keeps the list current without
# hammering the DB on every autocomplete interaction. Entries are stored
# as (name, value) tuples, which is the shape lightbulb's AutocompleteContext
# expects (lightbulb.Choice is for slash-command option choices, not
# autocomplete responses).
_SEASON_CHOICES_TTL_S = 300
_season_choices_cache: TTLCache = TTLCache(maxsize=1, ttl=_SEASON_CHOICES_TTL_S)
_CURRENT_CHOICE: Tuple[str, str] = ("Current season", "current")


async def _load_season_choices() -> List[Tuple[str, str]]:
    """Build the season choice list from the history DB."""
    try:
        seasons = await AnimeCornerHistoryManager.list_available_seasons()
    except Exception:
        log.warning(
            "Failed to load seasons for the anime-of-the-week-history "
            "autocomplete; only 'current' will be offered:\n"
            + traceback.format_exc()
        )
        return [_CURRENT_CHOICE]
    choices: List[Tuple[str, str]] = [_CURRENT_CHOICE]
    for season, year in seasons[:24]:
        choices.append((f"{season.title()} {year}", f"{season} {year}"))
    return choices


async def anime_of_the_week_season_autocomplete(
    ctx: lightbulb.AutocompleteContext,
) -> None:
    """Season autocomplete for /anime-of-the-week-history."""
    try:
        choices = _season_choices_cache.get("seasons")
        if choices is None:
            choices = await _load_season_choices()
            _season_choices_cache["seasons"] = choices
        needle = (ctx.focused.value or "").lower()
        if not needle:
            await ctx.respond(choices)
            return
        # Always keep "current" reachable, then append needle matches.
        filtered: List[Tuple[str, str]] = []
        if needle in _CURRENT_CHOICE[1] or needle in _CURRENT_CHOICE[0].lower():
            filtered.append(_CURRENT_CHOICE)
        for c in choices[1:]:
            if len(filtered) >= 25:
                break
            if needle in c[1].lower() or needle in c[0].lower():
                filtered.append(c)
        await ctx.respond(filtered or choices)
    except Exception:
        log.warning(
            f"anime-of-the-week-history season autocomplete failed:\n"
            f"{traceback.format_exc()}"
        )
        await ctx.respond([_CURRENT_CHOICE])


@loader.command
class Anime(
    SlashCommand,
    name="anime",
    description="Search for an Anime by name",
    default_member_permissions=None,
    hooks=[sliding_window(5, 1, "user")]
):
    name = lightbulb.string("name", "The name of the Anime")

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        pag = AnimePaginator()
        await ctx.defer()
        try:
            await pag.start(ctx, self.name)
        except Exception:
            log = getLogger(__name__, "fetch_anime")
            log.debug(traceback.format_exc())
            url = "https://myanimelist.net/"
            code, error = await check_website(url)
            if code == 200:
                await ctx.respond(
                    f"Seems like you haven't typed in something anime like.",
                    ephemeral=True
                )
            else:
                await ctx.respond(
                    f"Seems like [MyAnimeList]({url}) is down. Please try again later.\n_{code} - {error}_",
                    ephemeral=True,
                    attachments=[hikari.files.URL(url=MAGIC_ERROR_MONSTER, filename="error-monster.png")],
                )


@loader.command
class AnimeOfTheWeekHistory(
    SlashCommand,
    name="anime-of-the-week-history",
    description="Show the rank history of animes from the Anime Corner Top 10 weekly ranking",
    default_member_permissions=None,
    hooks=[sliding_window(30, 5, "user")],
):
    season = lightbulb.string(
        "season",
        "Which season of Anime of the Week history to show (defaults to the current season)",
        autocomplete=anime_of_the_week_season_autocomplete,
        default="current",
    )

    @invoke
    async def callback(self, _ctx: lightbulb.Context, ctx: InuContext):
        await ctx.defer()
        try:
            since, until, _season, _year = parse_season_arg(self.season)
        except ValueError as exc:
            raise BotResponseError(str(exc), ephemeral=True)
        pag = AnimeCornerHistoryPaginator(since=since, until=until, ctx=ctx)
        try:
            await pag.start(ctx)
        except BotResponseError:
            raise
        except Exception:
            log.debug(traceback.format_exc())
            raise BotResponseError(
                "Couldn't load the Anime of the Week history. Make sure the "
                "AnimeCorner task has run at least once.",
                ephemeral=True,
            )


# @loader.command
# class Manga(
#     SlashCommand,
#     name="manga",
#     description="get information of a Manga by name",
#     default_member_permissions=None,
#     hooks=[sliding_window(8, 1, "user")]
# ):
#     name = lightbulb.string("name", "The name of the Manga")

#     @invoke
#     async def callback(self, _: lightbulb.Context, ctx: InuContext):
#         pag = MangaPaginator()
#         await ctx.defer()
#         try:
#             await pag.start(ctx, self.name)
#         except Exception:
#             log = getLogger(__name__, "fetch_manga")
#             log.debug(traceback.format_exc())
#             url = "https://myanimelist.net/"
#             code, error = await check_website(url)
#             if code == 200:
#                 await ctx.respond(
#                     f"Seems like you haven't typed in something manga like.",
#                     ephemeral=True
#                 )
#             else:
#                 await ctx.respond(
#                     f"Seems like [MyAnimeList]({url}) is down. Please try again later.\n_{code} - {error}_",
#                     ephemeral=True,
#                     attachments=[hikari.files.URL(url=MAGIC_ERROR_MONSTER, filename="error-monster.png")],
#                 )