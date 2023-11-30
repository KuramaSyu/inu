import hikari
import lightbulb
from lightbulb import OptionModifier as OM
from lightbulb import commands, context


from utils import (
    ShowPaginator, 
    MoviePaginator
)
from core import (
    Inu, 
    getLogger,
    get_context
)

log = getLogger(__name__)

plugin = lightbulb.Plugin("Name", "Description")
bot: Inu

@plugin.command
@lightbulb.option("name", "name of tv show")
@lightbulb.command("tv-show", "Search a tv show (TMDB)")
@lightbulb.implements(commands.SlashCommand)
async def search_show(_ctx: context.Context):
    ctx = get_context(_ctx.event)
    await ctx.defer()
    pag = ShowPaginator()
    await pag.start(ctx, _ctx.options.name)


@plugin.command
@lightbulb.option("name", "name of movie")
@lightbulb.command("movie", "Search a movie (TMDB)")
@lightbulb.implements(commands.SlashCommand)
async def search_movie(_ctx: context.Context):
    ctx = get_context(_ctx.event)
    await ctx.defer()
    pag = MoviePaginator()
    await pag.start(ctx, _ctx.options.name)



def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

