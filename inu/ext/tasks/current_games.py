from abc import ABC, abstractmethod
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
from hikari.presences import ActivityType
import lightbulb
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from asyncpg import StringDataRightTruncationError

from utils import Reddit
from core.db import Database
from core import Inu
from utils import CurrentGamesManager, Games
from utils import Columns as Col


from core import getLogger

plugin = lightbulb.Loader()
log = getLogger(__name__)
bot = Inu.instance

# Mapping from guild_id to a mapping from game name to amount of users playing it
games: Dict[int, Dict[str, int]] = {}
banned_act_names = ["Custom Status", "Hang Status", *Games.DONT_RECORD]

async def fetch_current_games(bot: Inu):
    games: Dict[int, Dict[str, int]] = {}
    guild: hikari.OwnGuild
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
                        act_name = emulation_format(act_name, activity)
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

def emulation_format(emulator: str, activity: hikari.RichActivity) -> str:
    """Goes through EmulationFormats to properly format to Game (Emulator)"""
    log.debug(f"emulator: {emulator}, activity: {repr(activity)}, details: {activity.details}")
    strategies = [RyujinxFormat, YuzuFormat]
    for s in strategies:
        s = s(emulator, activity)
        if emulator in s.emulator_list:
            title = s.make_title()
            log.debug(f"{title}")
            return title
    return emulator

class EmulationFormat(ABC):
    def __init__(self, emulator: str, activity: hikari.RichActivity) -> None:
        self.emulator = emulator
        self.activity = activity

    @property
    @abstractmethod
    def emulator_list(self) -> List[str]:
        ...

    @abstractmethod
    def extract_game(self) -> str | None:
        ...
    
    def make_title(self) -> str:
        """Returns string in format: Game (Emulator)"""
        game_name = self.extract_game()
        if game_name:
            return f"{game_name} ({self.emulator})"
        return self.emulator


class RyujinxFormat(EmulationFormat):
    def extract_game(self) -> str | None:
        if not self.activity.details:
            return None

        game_name = self.activity.details.splitlines()[0]
        if game_name.startswith("Playing "):
            game_name = game_name[8:]
        return game_name

    @property
    def emulator_list(self) -> List[str]:
        return ["Ryujinx"]

class YuzuFormat(EmulationFormat):
    def extract_game(self) -> str | None:
        return self.activity.state

    @property
    def emulator_list(self) -> List[str]:
        return ["Yuzu", "Citron", "Sudachi", "Suyu"]


async def log_current_activity(bot: Inu):
    for _, guild in bot.cache.get_guilds_view().items():
        log.debug(f"activity for {guild.name}: {await CurrentGamesManager.fetch_games(guild.id, datetime.now() - timedelta(days=30))}")

# TODO: add a task to delete games older than a certain time



@plugin.listener(ShardReadyEvent)
async def load_tasks(event: ShardReadyEvent):
    # return if it's already scheduled
    try:
        if [True for job in bot.scheduler.get_jobs() if job.name == fetch_current_games.__name__ ]:
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
        await fetch_current_games(bot)
        trigger = IntervalTrigger(minutes=10)
        log.info(f"scheduled fetch_current_games: {trigger}", prefix="init")
        bot.scheduler.add_job(fetch_current_games, trigger, args=[bot])
       # log.info("scheduled fetch_current_games every 10 minutes", prefix="init")
    except Exception:
        log.critical(traceback.format_exc())