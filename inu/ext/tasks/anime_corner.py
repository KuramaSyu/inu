
from typing import *
import asyncio
import logging
from datetime import datetime, timedelta, time, date
import traceback

import lightbulb
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from humanize import naturaldelta
from core import Table, getLogger, Inu, stopwatch
from utils import Reddit, AnimeCornerAPI, AnimeCornerPaginator2, AnimeCornerView



log = getLogger(__name__)
METHOD_SYNC_TIME: int = 60*60*6
SYNCING = False
TARGET_TIME = time(18,00)
TRIGGER_NAME = "Anime Corner Trigger"
bot: Inu = Inu.instance
METHOD_SYNC_TIME = bot.conf.commands.anime_corner_sync_time * 60 * 60  # type: ignore



plugin = lightbulb.Loader()

@plugin.listener(hikari.StartedEvent)
async def load_tasks(event: hikari.StartedEvent):
    global SYNCING
    if SYNCING:
        return
    SYNCING = True
    await asyncio.sleep(3)
    await method()
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    await init_method()
    await defer_trigger_to_time()


async def defer_trigger_to_time(target_time: time | None = TARGET_TIME):
    target_datetime = None
    if target_time is not None:
        current_time = datetime.now().time()
        target_datetime = datetime.combine(date.today(), target_time)

        if target_datetime.time() < current_time:
            target_datetime += timedelta(days=1)

        wait_time = (target_datetime - datetime.now()).total_seconds()
        log.info(f"Waiting for {naturaldelta(timedelta(seconds=wait_time))} to shedule the {TRIGGER_NAME}", prefix="task")
    trigger = IntervalTrigger(seconds=METHOD_SYNC_TIME, start_date=target_datetime)
    bot.scheduler.add_job(method, trigger)
    

async def init_method():
    pass

@stopwatch(
    note=f"[CACHE] Task: Fetching Anime Corner Ranking (Reddit + Anime Corner)", 
    cache_threshold=timedelta(microseconds=1)
)
async def method():
    url = None
    try:
        submission = await Reddit.get_anime_of_the_week_post()
        # build pag + API
        pag = AnimeCornerPaginator2()
        pag.submission = submission
        pag.title = submission.title
        url = pag.anime_corner_url
        api = AnimeCornerAPI()

        await api.fetch_ranking(url)  # fetches the ranking from Anime Corner
        await pag.fetch_matches()  # fetches every single anime match
    except Exception as e:
        log.error(
            f"[CACHE] Error while fetching Anime Corner ranking with URL `{url}`\n",
            f"{traceback.format_exc()}",
            prefix="task"
        )
    
