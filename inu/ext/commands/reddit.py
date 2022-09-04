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
from core import getLogger, stopwatch, BotResponseError, Inu

log = getLogger(__name__)


plugin = lightbulb.Plugin("Reddit things", include_datastore=True)
plugin.d.last_update = 0
plugin.d.updating = False
bot: Inu

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
    'AnimeBooty': {
        'hot': 13,
        'top': 5,
    },
    'animelegs': {
        'hot': 5,
        'top': 1,
    },
    'Atago':  {
        'hot': 1,
        'top': 1,
    },
    'bluehairhentai':  {
        'hot': 3,
        'top': 3,
    },
    'chiisaihentai':  {
        'hot': 10,
        'top': 10,
    },
    'ecchi':  {
        'hot': 20,
        'top': 15,
    },
    'hentai':  {
        'hot': 20,
        'top': 6,
    },
    'HentaiBlowjob':  {
        'hot': 4,
        'top': 4,
    },
    'HentaiSchoolGirls':  {
        'hot': 3,
        'top': 3,
    },
    'MasturbationHentai':  {
        'hot': 10,
        'top': 5,
    },
    'Nekomimi':  {
        'hot': 15,
        'top': 10,
    },
    'Sukebei':  {
        'hot': 12,
        'top': 5,
    },
    'thighdeology':  {
        'hot': 15,
        'top': 6,
    },
    'WaifusOnCouch':  {
        'hot': 3,
        'top': 2,
    },
    'pantsu':  {
        'hot': 13,
        'top': 5,
    }, # fanservice
    # 'ahegao':  {
    #     'hot': 1,
    #     'top': 1,
    # },
    # 'yuri': 5,
    # 'ZettaiRyouiki': 5,
    'Paizuri':  {
        'hot': 5,
        'top': 3,
    },
    'CumHentai':  {
        'hot': 8,
        'top': 5,
    },
}
# list with all submissions, updated every 3 hours
hentai_cache: List[asyncpraw.models.Submission] = []
_old_hentai_cache: set[asyncpraw.models.Submission] = set()
# Dict[guild_id, List[hentai_cache_indexes]]
hentai_cache_indexes: Dict[int, List[int]] = {

}



SYNCING = False

@plugin.listener(hikari.ShardReadyEvent)
async def load_tasks(event: hikari.ShardReadyEvent):
    global SYNCING
    if SYNCING:
        return
    else:
        SYNCING = True
    await _update_pictures(subreddits)

    trigger = IntervalTrigger(hours=10)
    plugin.bot.scheduler.add_job(_update_pictures, trigger, args=[subreddits])
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)

@plugin.command
@lightbulb.add_cooldown(1, 4, lightbulb.UserBucket)
@lightbulb.command("hentai", "sends a hentai picture from Reddit")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def hentai(ctx: Context):
    '''
    Sends a Hentai picture
    Parameters:
    [Optional] subreddit: The subreddit u want a picture from - Default: A list of Hentai Subreddits
    '''
    id = ctx.guild_id or ctx.channel_id
    def check_index_list():
        if not hentai_cache_indexes.get(id, []):
            hentai_cache_indexes[id] = [i for i in range(len(hentai_cache))]
            random.shuffle(hentai_cache_indexes[id])
    check_index_list()
    # needs to be in a function, otherwise async would cause problems
    # when command is called very fast
    def get_submission():
        return hentai_cache[hentai_cache_indexes[id].pop(-1)]
    submission = get_submission()
    return await send_pic(ctx, "", footer=True, amount=10, submission=submission)


    #await .send_pic(ctx, subreddit, footer=False)


@stopwatch(
    lambda: (
        f"cached {H.plural_('submission', len(hentai_cache), with_number=True)} "
        f"| max was: {sum([x for n in subreddits.values() for _, x in n.items()])} "
        f"| new added: {len(set(hentai_cache) - _old_hentai_cache)}"
    )
)
async def _update_pictures(subreddits: Dict[str, int], minimum: int = 5):
    new_cache: List[asyncpraw.models.Submission] = []
    async def update(subreddit, amount: int):
        subs = await Reddit._fetch_posts(
            subreddit=subreddit,
            hot=True,
            top=False,
            time_filter="day",
            minimum=amount["hot"],
        )
        hot_only_len = len(subs)
        subs.extend( 
            list(set(
                    await Reddit._fetch_posts(
                    subreddit=subreddit,
                    hot=False,
                    top=True,
                    time_filter="day",
                    minimum=amount["top"],
                )
            ) - set(subs))
        )
        log.debug(f"subreddit: {subreddit:<20} | amount: {len(set(subs)):<3} | unique in top: {len(subs) - hot_only_len}")
        new_cache.extend(subs)
        # log.debug(f"{hentai_cache=}")
    tasks: List[asyncio.Task] = []
    for subreddit, amount in subreddits.items():
        tasks.append(
            asyncio.create_task(update(subreddit, amount))
        )
    L = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    global hentai_cache, _old_hentai_cache, hentai_cache_indexes
    _old_hentai_cache = set(hentai_cache)
    hentai_cache = new_cache
    hentai_cache_indexes = {}
    

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
    if (
        post.over_18 
        and ctx.guild_id 
        and not (ctx.get_channel() or await bot.rest.fetch_channel(ctx.channel_id)).is_nsfw  # type: ignore
    ):
        raise BotResponseError(
            f"This is NSFW content. Please post into an according channel for it",
            ephemeral=True
        )
    embed = hikari.Embed()
    embed.title = post.title
    embed.set_image(post.url)
    if footer:
        embed.description = f'[{post.subreddit_name_prefixed}](https://www.reddit.com/{post.subreddit._path})'
    await ctx.respond(embed=embed)


def load(inu: lightbulb.BotApp):
    inu.add_plugin(plugin)
    global bot
    bot = inu
    

