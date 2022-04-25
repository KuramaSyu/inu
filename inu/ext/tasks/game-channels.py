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

from utils import Reddit
from core.db import Database
from core import Inu
from utils import CurrentGamesManager
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

async def fetch_current_games(bot: Inu):
    games: Dict[int, Dict[str, int]] = {}
    banned_act_names = ["Custom Status"]
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
                    if not games.get(guild.id):
                        games[guild.id] = {}
                    if act_name in games[guild.id]:
                        games[guild.id][act_name] += 1
                    else:
                        games[guild.id][act_name] = 1
    for guild_id, game_dict in games.items():
        for game, amount in game_dict.items():
            await CurrentGamesManager.add(guild_id, game, amount)

async def log_current_activity(bot: Inu):
    for _, guild in await bot.cache.get_guilds_view().items():
        log.debug(f"activity for {guild.name}: {await CurrentGamesManager.fetch_games(guild.id, datetime.now() - timedelta(days=30))}")

# TODO: add a task to delete games older than a certain time

@plugin.listener(ShardReadyEvent)
async def load_tasks(event: ShardReadyEvent):
    try:
        await asyncio.sleep(10)
        log.debug("fetching current games")
        await fetch_current_games(plugin.bot)
        res = await CurrentGamesManager.fetch_games(
            538398443006066728, 
            datetime.now() - timedelta(days=30)
        )
        log.debug(res)
        trigger = IntervalTrigger(minutes=10)
        plugin.bot.scheduler.add_job(fetch_current_games, trigger, args=[plugin.bot])
        log.debug(plugin.bot.scheduler.running)
    except Exception:
        log.critical(traceback.format_exc())


def load(bot: Inu):
    bot.add_plugin(plugin)