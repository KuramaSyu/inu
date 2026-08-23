import asyncio
from datetime import datetime, timedelta
from typing import *
import hikari
import lightbulb
import traceback

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

# Discord caps a single slash-command option at 25 choices. We reserve the
# first slot for the synthetic "current" entry (the default) and fill the
# remaining 24 with the most recent (season, year) pairs the history table
# actually has data for. The list is mutated in-place by
# :func:`refresh_season_choices` once the database is reachable at bot
# startup — lightbulb reads the choices by reference at sync time, so
# mutating the list before Discord sync produces the right registration
# payload.
ANIME_OF_WEEK_SEASON_CHOICES: List[lightbulb.Choice] = [
    lightbulb.Choice("Current season", "current"),
]


async def refresh_season_choices() -> None:
    """Populate :data:`ANIME_OF_WEEK_SEASON_CHOICES` from the history DB.

    Called once during bot startup (after the DB is connected, before the
    slash commands are synced to Discord). Discord caps a single option at
    25 choices, so we keep the first slot for the synthetic ``"current"``
    entry and fill the remaining 24 with the most recent (season, year)
    pairs in the database.
    """
    try:
        seasons = await AnimeCornerHistoryManager.list_available_seasons()
    except Exception:
        log.warning(
            "Failed to load season list for the anime-of-the-week-history "
            "command; only the 'current' choice will be available:\n"
            + traceback.format_exc()
        )
        return
    max_extra = 24  # 25 slots - 1 reserved for the "current" choice
    ANIME_OF_WEEK_SEASON_CHOICES[:] = [
        lightbulb.Choice("Current season", "current"),
    ]
    for season, year in seasons[:max_extra]:
        label = f"{season.title()} {year}"
        value = f"{season} {year}"
        ANIME_OF_WEEK_SEASON_CHOICES.append(lightbulb.Choice(label, value))
    log.debug(
        f"anime-of-the-week-history: loaded {len(ANIME_OF_WEEK_SEASON_CHOICES)} "
        f"season choice(s) from the database.",
        prefix="init",
    )

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
        choices=ANIME_OF_WEEK_SEASON_CHOICES,
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