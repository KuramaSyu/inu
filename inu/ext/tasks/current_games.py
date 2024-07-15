import asyncio
import typing
from typing import *
import random
from datetime import datetime, timedelta
import time as tm
import traceback
import logging
from pprint import pformat

import hikari
from hikari.events.shard_events import ShardReadyEvent
import lightbulb
from lightbulb import Plugin
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from asyncpg import StringDataRightTruncationError

from utils import Reddit
from core.db import Database
from core import Inu
from utils import CurrentGamesManager, Games
from utils import Columns as Col


from core import getLogger

log = getLogger(__name__)

plugin = lightbulb.Plugin(
    "Auto Category", 
    "Creates a category which will be updated with games which are played", 
    include_datastore=True
)

# Mapping from guild_id to a mapping from game name to amount of users playing it
games: Dict[int, Dict[str, int]] = {}
banned_act_names = ["Custom Status", "Hang Status"]

async def fetch_current_games(bot: Inu):
    games: Dict[int, Dict[str, int]] = {}
    guild: hikari.Guild
    now = datetime.now()
    if now.hour == 0:
        # TODO: write games to database
        games = {}
    for guild in await bot.rest.fetch_my_guilds():
        for member in await bot.rest.fetch_members(guild.id):
            if (presence := member.get_presence()) and not member.is_bot:
                for activity in presence.activities:
                    act_name = activity.name
                    if act_name in banned_act_names:
                        continue
                    if act_name in Games.EMULATORS and activity.details:
                        # if the activity is an emulator, add the game name to the activity name
                        # format: "Game (Emulator)"
                        act_name = f"{activity.details.splitlines()[0]} ({act_name})"
                    if not games.get(guild.id):
                        games[guild.id] = {}
                    if act_name in games[guild.id]:
                        games[guild.id][act_name] += 1
                    else:
                        games[guild.id][act_name] = 1
    for guild_id, game_dict in games.items():
        for game, amount in game_dict.items():
            try:
                await CurrentGamesManager.add(guild_id, game, amount)
            except StringDataRightTruncationError:
                log.warning(f"Current Games ignored: `{game}` with len of {len(game)}", prefix="task")
                banned_act_names.append(game)



async def log_current_activity(bot: Inu):
    for _, guild in await bot.cache.get_guilds_view().items():
        log.debug(f"activity for {guild.name}: {await CurrentGamesManager.fetch_games(guild.id, datetime.now() - timedelta(days=30))}")

# TODO: add a task to delete games older than a certain time



@plugin.listener(ShardReadyEvent)
async def load_tasks(event: ShardReadyEvent):
    # return if it's already scheduled
    try:
        if [True for job in plugin.bot.scheduler.get_jobs() if job.name == fetch_current_games.__name__ ]:
            log.info("fetch_current_games already scheduled - skipping")
            return
    except Exception:
        log.error(traceback.format_exc())
    try:
        # sleep until its XX:X5
        now = datetime.now()
        seconds_until_min_is_5 = (5 - now.minute % 5) * 60 - now.second
        log.info(f"sleep for {timedelta(seconds=seconds_until_min_is_5)} until fetching first current games", prefix="init")
        await asyncio.sleep(seconds_until_min_is_5)
        await fetch_current_games(plugin.bot)
        trigger = IntervalTrigger(minutes=10)
        log.info(f"scheduled fetch_current_games: {trigger}", prefix="init")
        plugin.bot.scheduler.add_job(fetch_current_games, trigger, args=[plugin.bot])
       # log.info("scheduled fetch_current_games every 10 minutes", prefix="init")
    except Exception:
        log.critical(traceback.format_exc())


def load(bot: Inu):
    bot.add_plugin(plugin)