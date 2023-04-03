import traceback
from typing import *

from jikanpy import AioJikan
import hikari
import lightbulb
from lightbulb import commands, context
from lightbulb.commands import OptionModifier as OM
from matplotlib.pyplot import title

from utils import (
    Human, 
    Paginator,
    AnimePaginator, 
    AnimeCharacterPaginator,
    MangaPaginator,
)
from core import getLogger, get_context

log = getLogger(__name__)
plugin = lightbulb.Plugin("Anime", "Expends bot with anime based commands")



@plugin.command
@lightbulb.add_cooldown(5, 1, lightbulb.UserBucket)
@lightbulb.option("name", "the name of the Anime", type=str, modifier=OM.CONSUME_REST)
@lightbulb.command("anime", "get information of an Anime by name")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def fetch_anime(_ctx: context.Context):
    pag = AnimePaginator()
    ctx = get_context(_ctx.event)
    await ctx.defer()
    try:
        await pag.start(ctx, _ctx.options.name)
    except Exception:
        log = getLogger(__name__, "fetch_anime")
        log.debug(traceback.format_exc())
        await ctx.respond(
            f"Seems like you haven't typed in something anime like.",
            ephemeral=True
        )


# @fetch_anime.set_error_handler()
# async def anime_on_error(e: lightbulb.CommandErrorEvent):
#     await e.context.respond(
#         f"Seems like you haven't typed in something anime like.",
#         flags=hikari.MessageFlag.EPHEMERAL
#     )
#     return True


# @plugin.command
# @lightbulb.add_cooldown(8, 1, lightbulb.UserBucket)
# @lightbulb.option("name", "the name of the Anime character", type=str, modifier=OM.CONSUME_REST)
# @lightbulb.command("anime-character", "get information of an Anime character by name", aliases=["character"], auto_defer=True)
# @lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
# async def fetch_anime_character(ctx: context.Context):
#     try:
#         pag = AnimeCharacterPaginator()
#     except Exception:
#         log = getLogger(__name__, "fetch_anime_character")
#         log.debug(traceback.format_exc())
#         return
#     await pag.start(ctx, ctx.options.name)



@plugin.command
@lightbulb.add_cooldown(8, 1, lightbulb.UserBucket)
@lightbulb.option("name", "the name of the Manga", type=str, modifier=OM.CONSUME_REST)
@lightbulb.command("manga", "get information of an Manga by name", auto_defer=True)
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def fetch_manga(ctx: context.Context):
    try:
        pag = MangaPaginator()
    except Exception:
        log = getLogger(__name__, "fetch_manga")
        log.debug(traceback.format_exc())
        return
    await pag.start(ctx, ctx.options.name)



def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)