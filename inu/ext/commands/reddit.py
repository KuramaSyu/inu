import asyncio
import typing
from typing import (
    List,
    Dict,
    Any,
    Optional,
    Union
)
import time as tm
import random
import logging

import asyncpraw
import hikari
import lightbulb
from lightbulb.context import Context
from lightbulb import commands
from utils.rest import Reddit

from core import getLogger

log = getLogger(__name__)


plugin = lightbulb.Plugin("Reddit things", include_datastore=True)

plugin.d.last_update = 0
plugin.d.updating = False

@plugin.listener(hikari.ShardReadyEvent)
async def on_ready(event: hikari.ShardReadyEvent):
    await Reddit.init_reddit_credentials(plugin.bot)
    
@plugin.command
@lightbulb.add_cooldown(1, 3, lightbulb.UserBucket)
@lightbulb.option("subreddit", "A Subreddit where the pic should come from", default="")
@lightbulb.command("pic", "sends a nice picture from Reddit", aliases = ['rand_pic', 'picture'])
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def pic(ctx: Context):
    '''
    Sends a nice Picture
    Parameters:
    [Optional] subreddit: The subreddit u want a picture from - Default: A list of picture Subreddits
    '''
    subreddit = ctx.options.subreddit
    if subreddit == '':
        subreddit = random.choice(['itookapicture','CityPorn','EarthPorn', 'Pictures'])
    await send_pic(ctx, subreddit)


@plugin.command
@lightbulb.add_cooldown(1, 3, lightbulb.UserBucket)
@lightbulb.option("subreddit", "A Subreddit where the pic should come from", default="")
@lightbulb.command("meme", "sends a meme from Reddit")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def memes(ctx: Context):
    '''
    Sends a meme
    Parameters:
    [Optional] subreddit: The subreddit u want a picture from - Default: A list of meme Subreddits
    '''
    subreddit = ctx.options.subreddit
    if subreddit == '':
        subreddit = random.choice(['memes','funny'])
    await send_pic(ctx, subreddit)



@plugin.command
@lightbulb.add_cooldown(1, 4, lightbulb.UserBucket)
@lightbulb.option("subreddit", "A Subreddit where the pic should come from", default=None)
@lightbulb.command("hentai", "sends a hentai picture from Reddit")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def hentai(ctx: Context):
    '''
    Sends a Hentai picture
    Parameters:
    [Optional] subreddit: The subreddit u want a picture from - Default: A list of Hentai Subreddits
    '''
    subreddit = ctx.options.subreddit
    amount = 5
    subreddits = []
    if (
        plugin.d.last_update - float(3*60*60) - 120 < tm.time() 
        and not plugin.d.updating
    ):
        amount = 1
    if not subreddit:
        subreddit = random.choice(
            (subreddits := [
                'animearmpits', 'AnimeBooty',
                'animelegs', 'Atago', 'bluehairhentai', 'chiisaihentai', 'ecchi',
                'hentai', 'HentaiBlowjob', 'HentaiCumsluts', 'HentaiSchoolGirls',
                'MasturbationHentai', 'Nekomimi', 'Sukebei', 'thighdeology', 'WaifusOnCouch',
            ])
        )
    await send_pic(ctx, subreddit, footer=False, amount=amount)
    if plugin.d.last_update + float(3*60*60) < tm.time() and subreddits:
        plugin.d.last_update = float(tm.time()) + float(3*60*60)
        await _update_pictures(subreddits=subreddits)
    #await .send_pic(ctx, subreddit, footer=False)

async def _update_pictures(subreddits: List[str]):
    plugin.d.updating = False
    async def update(subreddit):
        _ = await Reddit.get_posts(
            subreddit=subreddit,
            hot=True,
            minimum=5,
        )
    tasks: List[asyncio.Task] = []
    for subreddit in subreddits:
        asyncio.create_task(update(subreddit))
    L = await asyncio.gather(*tasks)
    plugin.d.updating = True
    log.debug("cached hentai urls")
    

async def send_pic(ctx: Context, subreddit: str, footer: bool = True, amount: int= 5):
    posts = await Reddit.get_posts(
        subreddit=subreddit,
        hot=True,
        minimum=amount,
    )
    try:
        post = random.choice(posts)
    except IndexError:
        return await ctx.respond(f"`{subreddit}` is currently not reachable or has too less pictures")
    embed = hikari.Embed()
    embed.title = post.title
    embed.set_image(post.url)
    if footer:
        embed.set_footer(text=f"r/{subreddit}")
    await ctx.respond(embed=embed)


def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)

