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
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger

from utils import Human as H
from core import getLogger, stopwatch

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


subreddits: Dict[str, int] = {
    'AnimeBooty': 12,
    'animelegs': 10,
    'Atago': 5,
    'bluehairhentai': 5,
    'chiisaihentai': 10,
    'ecchi': 20,
    'hentai': 20,
    'HentaiBlowjob': 5,
    'HentaiSchoolGirls': 5,
    'MasturbationHentai': 10,
    'Nekomimi': 15,
    'Sukebei': 12,
    'thighdeology': 15,
    'WaifusOnCouch': 5,
    'pantsu': 10,
    'ahegao': 3,
    'yuri': 5,
    'ZettaiRyouiki': 9,
    'Paizuri': 5,
    'CumHentai': 8,
}
# list with all submissions, updated every 3 hours
hentai_cache: List[asyncpraw.models.Submission] = []
_old_hentai_cache: set[asyncpraw.models.Submission] = set()



SYNCING = False

@plugin.listener(hikari.ShardReadyEvent)
async def load_tasks(event: hikari.ShardReadyEvent):
    global SYNCING
    if SYNCING:
        return
    else:
        SYNCING = True
    await _update_pictures(subreddits)

    trigger = IntervalTrigger(hours=24)
    plugin.bot.scheduler.add_job(_update_pictures, trigger, args=[subreddits])
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)

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
    if not subreddit:
        # all hentai subreddits: "https://www.reddit.com/r/hentai/wiki/hentai_subreddits/#wiki_subreddits_based_on..."
    #     subreddit = random.choice(
    #         [sub  for sub, amount in subreddits.items() for _ in range(amount)]
    #     )
        submission = random.choice(hentai_cache)
        return await send_pic(ctx, None, footer=False, amount=10, submission=submission)
    await send_pic(ctx, subreddit, footer=False, amount=10)


    #await .send_pic(ctx, subreddit, footer=False)


@stopwatch(
    lambda: (
        f"cached {H.plural_('submission', len(hentai_cache), with_number=True)} "
        f"| goal was: {sum([n for n in subreddits.values()])} "
        f"| set amount: {len(set(hentai_cache))} "
        f"| new added: {len(set(hentai_cache) & _old_hentai_cache)}"
    )
)
async def _update_pictures(subreddits: Dict[str, int], minimum: int = 5):
    new_cache: List[asyncpraw.models.Submission] = []
    async def update(subreddit, amount: int):
        # just calling it, will trigger the cache
        subs = await Reddit._fetch_posts(
            subreddit=subreddit,
            hot=False,
            top=True,
            time_filter="day",
            minimum=amount,
        )
        new_cache.extend(subs)
        # log.debug(f"{hentai_cache=}")
    tasks: List[asyncio.Task] = []
    for subreddit, amount in subreddits.items():
        tasks.append(
            asyncio.create_task(update(subreddit, amount))
        )
    L = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
    global hentai_cache, _old_hentai_cache
    _old_hentai_cache = set(hentai_cache)
    hentai_cache = new_cache
    

async def send_pic(ctx: Context, subreddit: str, footer: bool = True, amount: int=5, submission: asyncpraw.models.Submission | None = None):
    if not submission:
        posts = await Reddit.get_posts(
            subreddit=subreddit,
            hot=True,
            minimum=amount,
        )
        try:
            post = random.choice(posts)
        except IndexError:
            return await ctx.respond(f"`{subreddit}` is currently not reachable or has too less pictures")
    else:
        post = submission
    embed = hikari.Embed()
    embed.title = post.title
    embed.set_image(post.url)
    if footer:
        embed.set_footer(text=f"r/{subreddit}")
    await ctx.respond(embed=embed)


def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)

