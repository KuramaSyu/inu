import hikari
import lightbulb
from lightbulb import commands, context, SlashCommand, invoke

from utils import (
    ShowPaginator, 
    MoviePaginator
)
from core import (
    Inu, 
    getLogger,
    InuContext,
    get_context
)

log = getLogger(__name__)

plugin = lightbulb.Loader()
bot: Inu

@plugin.command
class SearchShow(
    SlashCommand,
    name="tv-show",
    description="Search a tv show (TMDB)",
    dm_enabled=False,
    default_member_permissions=None,
):
    name = lightbulb.string("name", "name of tv show")

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await ctx.defer()
        pag = ShowPaginator()
        await pag.start(ctx, self.name)


@plugin.command
class SearchMovie(
    SlashCommand,
    name="movie",
    description="Search a movie (TMDB)",
    dm_enabled=False,
    default_member_permissions=None,
):
    name = lightbulb.string("name", "name of movie")

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await ctx.defer()
        pag = MoviePaginator()
        await pag.start(ctx, self.name)



