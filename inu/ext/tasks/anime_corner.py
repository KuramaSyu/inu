
from typing import *
import asyncio
import logging
from datetime import datetime, timedelta, time, date

import lightbulb
from lightbulb.commands.base import OptionModifier as OM
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from humanize import naturaldelta
from core import Table, getLogger, Inu, stopwatch
from utils import Reddit, AnimeCornerAPI, AnimeCornerPaginator2

log = getLogger(__name__)
METHOD_SYNC_TIME: int = 60*60*6
SYNCING = False
TARGET_TIME = time(16,00)
TRIGGER_NAME = "Anime Corner Trigger"
bot: Inu

plugin = lightbulb.Plugin("poll loader", "loads polls from database")

@plugin.listener(hikari.ShardReadyEvent)
async def load_tasks(event: hikari.ShardReadyEvent):
    global SYNCING
    if SYNCING:
        return
    else:
        SYNCING = True
    await asyncio.sleep(3)
    await method()
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    await init_method()
    await defer_trigger_to_time()


async def defer_trigger_to_time(target_time: time | None = TARGET_TIME):
    if target_time is not None:
        current_time = datetime.now().time()
        target_datetime = datetime.combine(date.today(), target_time)

        if target_datetime.time() < current_time:
            target_datetime += timedelta(days=1)

        wait_time = (target_datetime - datetime.now()).total_seconds()
        log.info(f"Waiting for {naturaldelta(timedelta(seconds=wait_time))} to shedule the {TRIGGER_NAME}")
        await asyncio.sleep(wait_time)

    trigger = IntervalTrigger(seconds=METHOD_SYNC_TIME)
    plugin.bot.scheduler.add_job(method, trigger)
    

async def init_method():
    pass

@stopwatch(
    note=f"Task: Fetching and caching Anime Corner Ranking (Reddit + Anime Corner)", 
    cache_threshold=timedelta(milliseconds=1200)
)
async def method():
    submission = await Reddit.get_anime_of_the_week_post()
    pag = AnimeCornerPaginator2()
    pag.submission = submission
    pag.title = submission.title
    url = pag.anime_corner_url
    api = AnimeCornerAPI()
    await api.fetch_ranking(url)

def load(inu: Inu):
    global bot
    bot = inu
    global METHOD_SYNC_TIME
    METHOD_SYNC_TIME = inu.conf.commands.poll_sync_time
    inu.add_plugin(plugin)