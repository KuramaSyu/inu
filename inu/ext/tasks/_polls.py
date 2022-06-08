import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging
import datetime
import time

import lightbulb
from lightbulb.commands.base import OptionModifier as OM
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils import POLL_SYNC_TIME, PollManager, Poll

from core import Table


plugin = lightbulb.Plugin("poll loader", "loads polls from database")

@plugin.listener(hikari.ShardReadyEvent)
async def load_tasks(event: hikari.ShardReadyEvent):
    await asyncio.sleep(3)
    await load_upcoming_reminders()

    trigger = IntervalTrigger(seconds=POLL_SYNC_TIME)
    plugin.bot.scheduler.add_job(load_upcoming_reminders, trigger)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)

async def load_upcoming_reminders():
    sql = """
    SELECT * FROM polls 
    WHERE expires < $1
    """
    poll_table = Table("polls")
    option_table = Table("poll_options")
    vote_table = Table("poll_votes")
    timestamp = datetime.datetime.fromtimestamp((time.time() + (POLL_SYNC_TIME)))
    records_polls = await poll_table.fetch(sql)

    #load
    for poll_record in records_polls:

        options = {}
        option_ids = []
        polls = {}
        poll_id = poll_record['poll_id']
        option_sql = f"""
        SELECT * FROM poll_options 
        WHERE poll_id = {poll_id}
        """
        option_records = await option_table.fetch(
            f"""
            SELECT * FROM poll_options 
            WHERE poll_id = {poll_id}
            """
        )
        for option_record in option_records:
            options[option_record['name']] = option_record['description']
            option_ids.append(option_record['option_id'])
        
        for vote_record in await vote_table.fetch(
            f"""
            SELECT * FROM poll_votes 
            WHERE poll_id = {poll_id}
            """
        ):
            if vote_record['option_id'] in polls.keys():
                polls[vote_record['option_id']].append(vote_record['user_id'])
            else:
                polls[vote_record['option_id']] = [vote_record['user_id']]

    PollManager.add_polls_to_set(records)

def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)