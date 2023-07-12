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
import traceback
from copy import deepcopy

import asyncpraw
import hikari
import lightbulb
from lightbulb.context import Context
from lightbulb import commands
from utils.rest import Reddit, AnimeCornerAPI
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger

from utils import Human as H
from utils.paginators import AnimeCornerPaginator, AnimeCornerPaginator2
from core import getLogger, stopwatch, BotResponseError, Inu, get_context

log = getLogger(__name__)


plugin = lightbulb.Plugin("Reddit things", include_datastore=True)
plugin.d.last_update = 0
plugin.d.updating = False
bot: Inu

@plugin.listener(hikari.ShardReadyEvent)
async def on_ready(event: hikari.ShardReadyEvent):
    await Reddit.init_reddit_credentials(plugin.bot)
    

subreddits: Dict[str, Dict[str, int]] = {
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
    }, 
    'genshinimpacthentai': {
        'hot': 20,
        'top': 10,
    },
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
HENTAI_DISABLED = True

@plugin.listener(hikari.ShardReadyEvent)
async def load_tasks(event: hikari.ShardReadyEvent):
    global SYNCING
    if SYNCING or HENTAI_DISABLED:
        return
    else:
        SYNCING = True
    await _update_pictures(subreddits)

    trigger = IntervalTrigger(hours=10)
    plugin.bot.scheduler.add_job(_update_pictures, trigger, args=[subreddits])
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)


# deactivated because of the reddit api changes
if not HENTAI_DISABLED:
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


@plugin.command
@lightbulb.add_cooldown(8, 1, lightbulb.UserBucket)
@lightbulb.command("anime-of-the-week", "get information of an Manga by name")
@lightbulb.implements(commands.SlashCommand)
async def anime_of_the_week(ctx: Context):
    ctx = get_context(ctx.event)
    await ctx.defer()
    try:
        submission = await Reddit.get_anime_of_the_week_post()
    except Exception:
        log.error(traceback.format_exc())
        return await ctx.respond("Well - I didn't found it")
    pag = AnimeCornerPaginator2()
    await pag.start(ctx, submission, submission.title)



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
    

async def send_pic(
    ctx: Context, 
    subreddit: str, 
    footer: bool = True, 
    amount: int=5, 
    submission: asyncpraw.models.Submission | None = None, 
    embed_template: hikari.Embed | None = None
):
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
    if embed_template:
        embed = deepcopy(embed_template)
    else:
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
    

