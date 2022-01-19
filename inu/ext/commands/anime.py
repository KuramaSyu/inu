import traceback
from typing import *


from jikanpy import AioJikan
import hikari
import lightbulb
from lightbulb import commands, context
from lightbulb.commands import OptionModifier as OM


from utils import Human, Paginator
from core import getLogger

log = getLogger(__name__)

async def search_anime(search: str) -> List[hikari.Embed]:
    def build_embeds(search_title: str, results: Dict):
        animes = []
        for anime in results["results"]:
            if search_title in anime["title"].lower():
                animes.append(anime)

        if animes == []:
            animes = results['results']

        embeds = []
        total = len(animes)
        for i, anime in enumerate(animes):
            embeds.append(
                (
                    hikari.Embed(
                        title=anime["title"],
                        description=f"more information on [MyAnimeList]({anime['url']})"
                    )
                    .add_field("Type", anime["type"], inline=True)
                    .add_field("Score", f"{anime['score']}/10", inline=True)
                    .add_field("Episodes", f"{anime['episodes']} {Human.plural_('episode', anime['episodes'])[0]}", inline=True)
                    .add_field("Description", anime['synopsis'], inline=False)
                    .add_field(
                        "Other",
                        (
                            f"finished: {Human.bool_('airing', twisted=True)}\n"
                            f"Members: {anime['members']}\n"
                            f"MyAnimeList ID: {anime['mal_id']}\n"
                            f"rated: {anime['rated']}\n"
                            f"start date: {anime['start_date'][:10] if anime['start_date'] else 'unknown'}\n"
                            f"end date: {anime['end_date'][:10] if anime['end_date'] else 'unknown'}\n"

                        )
                    )
                    .set_image(anime["image_url"])
                    .set_footer(f"page {i+1}/{total}")
                )
            )
        return embeds

    results = None

    async with AioJikan() as aio_jikan:
        results = await aio_jikan.search(search_type='anime', query=search)
    #pprint.pprint(results)
    embeds = build_embeds(search, results)
    if not embeds:
        return [hikari.Embed(title="Nothing found")]
    return embeds
    

plugin = lightbulb.Plugin("Anime", "Expends bot with anime based commands")

@plugin.command
@lightbulb.option("name", "the name of the Anime", type=str, modifier=OM.CONSUME_REST)
@lightbulb.command("anime", "get information of an Anime by name")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def fetch_anime(ctx: context.Context):
    try:
        pag = Paginator(
            page_s=await search_anime(ctx.options.name),
            timeout=8*10,
        )
    except Exception:
        log = getLogger(__name__, "fetch_anime")
        log.debug(traceback.format_exc())
        return
    await pag.start(ctx)

def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)