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
                    .add_field("Description", anime['synopsis'] or "No description", inline=False)
                    .add_field(
                        "Other",
                        (
                            f"finished: {Human.bool_('airing')}\n"
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
    embeds = build_embeds(search, results)
    if not embeds:
        return [hikari.Embed(title="Nothing found")]
    return embeds


def resp_to_embed(resp: dict) -> List[hikari.Embed]:
    data = resp["data"]
    embeds = []
    total = len(data)
    for i, anime in enumerate(data):
        embed = (
            hikari.Embed()
            .add_field("Type", anime["type"], inline=True)
            .add_field("Score", f"{anime['score']}/10", inline=True)
            .add_field("Episodes", f"{anime['episodes']} {Human.plural_('episode', anime['episodes'])[0]}", inline=True)
            .add_field("Rank", f"{anime['rank']}", inline=True)
            .add_field("Popularity", f"{anime['popularity']}", inline=True)
            .add_field("Rating", f"{anime['rating']}", inline=True)
            .add_field("Duration", f"{anime['duration']}", inline=True)
            .add_field(
                "Genres",
                f""" {', '.join(f"[{genre['name']}]({genre['url']})" 
                for genre in anime["genres"])}, {', '.join(f"[{genre['name']}]({genre['url']})" 
                for genre in anime["explicit_genres"])}
                """,
                inline=True,
            )
            .add_field(
                "Themes",
                ", ".join(
                    f"[{theme['name']}]({theme['url']})" for theme in anime["themes"]
                ),
                inline=True,
            )
            .add_field(
                "Other",
                (
                    f"finished: {Human.bool_('airing')}\n"
                    f"""Licensors: {", ".join(
                            f"[{licensor['name']}]({licensor['url']})" for licensor in anime["licensors"]
                        )
                    }\n"""
                    f"""Studios: {", ".join(
                            f"[{studio['name']}]({studio['url']})" for studio in anime["studios"]
                        )
                    }\n"""
                    f"""Producers: {", ".join(
                            f"[{producer['name']}]({producer['url']})" for producer in anime["producers"]
                        )
                    }\n"""
                    f"produce date: {anime['aired']['string']}\n"
                    f"MyAnimeList ID: {anime['mal_id']}\n"
                    f"""{", ".join(anime["title_synonyms"])}\n"""
                )
            )
            .set_image(anime["images"]["jpg"]["large_image_url"])
            .set_footer(f"page {i+1}/{total}")
        )
        embed.description = ""
        embed.title = ""
        if anime["title"] == anime["title_english"]:
            embed.title = anime["title"]
        elif anime["title_english"]:
            embed.title = anime["title_english"]
        else:
            embed.title = anime["title"]

            embed.description += f"original name: {anime['title']}"
        embed.description += f"\nmore information on [MyAnimeList]({anime['url']})"
        embed.description += f"\n\n{Human.short_text(anime['synopsis'], 1980)}"

        if anime["background"]:
            embed.add_field("Background", Human.short_text(anime["background"], 1020))

        if anime["trailer"]["url"]:
            embed.add_field("Trailer", f"[click here]({anime['trailer']['url']})")
        embeds.append(embed)
        for i, field in enumerate(embed.fields):
            if not field.value:
                embed.remove_field(i)
    return embeds
        

plugin = lightbulb.Plugin("Anime", "Expends bot with anime based commands")



@plugin.command
@lightbulb.add_cooldown(5, 1, lightbulb.UserBucket)
@lightbulb.option("name", "the name of the Anime", type=str, modifier=OM.CONSUME_REST)
@lightbulb.command("anime", "get information of an Anime by name", auto_defer=True)
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def fetch_anime(ctx: context.Context):
    try:
        pag = AnimePaginator()
    except Exception:
        log = getLogger(__name__, "fetch_anime")
        log.debug(traceback.format_exc())
        return
    await pag.start(ctx, ctx.options.name)

@fetch_anime.set_error_handler()
async def anime_on_error(e: lightbulb.CommandErrorEvent):
    await e.context.respond(
        f"Seems like you haven't typed in something anime like.",
        flags=hikari.MessageFlag.EPHEMERAL
    )
    return True



@plugin.command
@lightbulb.add_cooldown(8, 1, lightbulb.UserBucket)
@lightbulb.option("name", "the name of the Anime character", type=str, modifier=OM.CONSUME_REST)
@lightbulb.command("anime-character", "get information of an Anime character by name", aliases=["character"], auto_defer=True)
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def fetch_anime_character(ctx: context.Context):
    try:
        pag = AnimeCharacterPaginator()
    except Exception:
        log = getLogger(__name__, "fetch_anime_character")
        log.debug(traceback.format_exc())
        return
    await pag.start(ctx, ctx.options.name)



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