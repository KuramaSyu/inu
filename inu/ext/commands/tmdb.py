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
async def search_show(ctx: context.Context):
    pag = ShowPaginator()
    await pag.start(get_context(ctx.event), ctx.options.name)


@plugin.command
@lightbulb.option("name", "name of movie")
@lightbulb.command("movie", "Search a movie (TMDB)")
@lightbulb.implements(commands.SlashCommand)
async def search_movie(ctx: context.Context):
    pag = MoviePaginator()
    await pag.start(get_context(ctx.event), ctx.options.name)



def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

