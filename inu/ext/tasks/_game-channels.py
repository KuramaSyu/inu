import asyncio
import typing
from typing import *
import random
from datetime import datetime
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
from utils import DailyContentChannels
from utils import Columns as Col


from core import getLogger

log = getLogger(__name__)

plugin = lightbulb.Plugin(
    "Auto Category", 
    "Creates a category which will be updated with games which are played", 
    include_datastore=True
)

# Mapping from guild_id to a mapping from game name to playtime in hours
games: Dict[int, Dict[str, int]] = {}

async def fetch_current_games(bot: Inu, games: Dict[int, Dict[str, int]]):
    guild: hikari.Guild
    now = datetime.now()
    if now.hour == 0:
        # TODO: write games to database
        games = {}
    for guild in await bot.rest.fetch_my_guilds():
        for member in await bot.rest.fetch_members(guild.id):
            if (presence := member.get_presence()):
                for activity in presence.activities:
                    log.debug(f"{member.name} is playing {presence.activity.name}")
                    act_name = activity.name
                            

@plugin.listener(ShardReadyEvent)
async def load_tasks(event: ShardReadyEvent):
    DailyContentChannels.set_db(plugin.bot.db)
    await Reddit.init_reddit_credentials(plugin.bot)
    trigger = IntervalTrigger(minutes=10)
    plugin.bot.scheduler.add_job(fetch_current_games, trigger)
    log.debug(plugin.bot.scheduler.running)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)


def load(bot: Inu):
    bot.add_plugin(plugin)