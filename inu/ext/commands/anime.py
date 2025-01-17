import asyncio
from typing import *
from datetime import datetime
import hikari
import lightbulb
import traceback

from fuzzywuzzy import fuzz
from hikari import (
    Embed,
    ResponseType, 
    TextInputStyle,
    Permissions,
    ButtonStyle
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import Context, Loader, Group, SubGroup, SlashCommand, invoke
from lightbulb.prefab import sliding_window

from utils import (
    Human, 
    Paginator,
    AnimePaginator, 
    AnimeCharacterPaginator,
    MangaPaginator,
    check_website,
    MAGIC_ERROR_MONSTER
)
from core import getLogger, get_context, InuContext

log = getLogger(__name__)
loader = lightbulb.Loader()

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