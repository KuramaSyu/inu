from typing import *
import asyncio
import logging
from datetime import datetime, timedelta
import traceback

import lightbulb
from lightbulb.commands.base import OptionModifier as OM
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger

from utils import AutoroleManager, AutoroleAllEvent, VoiceActivityEvent, VoiceAutoroleCache
from core import Table, getLogger, Inu

log = getLogger(__name__)
METHOD_SYNC_TIME: int = 60*10
SYNCING = False
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
    await remove_expired_autoroles()

    trigger = IntervalTrigger(seconds=METHOD_SYNC_TIME)
    plugin.bot.scheduler.add_job(remove_expired_autoroles, trigger)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    await init_method()



async def init_method():
    await VoiceAutoroleCache.sync()



async def remove_expired_autoroles():
    """removes expired autoroles"""
    try:
        log.debug("removing expired autoroles")
        await AutoroleManager.remove_expired_autoroles(expires_in=METHOD_SYNC_TIME)
    except Exception:
        log.warning(traceback.format_exc())



@plugin.listener(hikari.MemberCreateEvent)
async def on_member_join(event: hikari.MemberCreateEvent):
    """used to call the default role callback"""
    events = await AutoroleManager.fetch_events(event.guild_id, AutoroleAllEvent)
    log.debug(f"found {len(events)} events for guild {event.guild_id}")
    tasks: List[asyncio.Task] = []
    for task in events:
        tasks.append(asyncio.create_task(task.callback(event)))
    await asyncio.gather(*tasks)



@plugin.listener(hikari.MemberDeleteEvent)
async def on_member_leave(event: hikari.MemberDeleteEvent):
    """used to call the member leave callback"""
    await AutoroleManager.delete_guild(event.guild_id)



@plugin.listener(hikari.VoiceStateUpdateEvent)
async def on_voice_state_update(event: hikari.VoiceStateUpdateEvent):
    """used to call the voice role callback"""
    if event.state.user_id == bot.cache.get_me().id:
        return
    if not(
        (event.old_state and not event.state.channel_id) 
        or (event.state.channel_id and not event.old_state)
    ):
        # nor a join or a leave event
        return
    
    if not event.guild_id in VoiceAutoroleCache:
        # to prevent to many db calls
        log.debug(f"guild {event.guild_id} not in VoiceAutoroleCache")
        return
    events: List[VoiceActivityEvent] = await AutoroleManager.fetch_events(event.guild_id, VoiceActivityEvent)
    log.debug(f"found {len(events)} events for guild {event.guild_id}")
    tasks: List[asyncio.Task] = []
    for task in events:
        tasks.append(asyncio.create_task(
            task.renew_user_duration(event.state.user_id, event.guild_id)
        ))
    await asyncio.gather(*tasks)


def load(inu: Inu):
    global bot
    bot = inu
    inu.add_plugin(plugin)