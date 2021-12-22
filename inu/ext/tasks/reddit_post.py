import asyncio
import typing
from typing import *
import random
import datetime
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
from utils.db import Database
from core import Inu
from utils import DailyContentChannels
from utils.r_channel_manager import Columns as Col


log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)


plugin = lightbulb.Plugin("Daily Reddit", "Sends daily automated Reddit pictures", include_datastore=True)
plugin.d.daily_content = {
    'time':{
        '1':['ComedyCemetery', 3],
        '2':['CrappyDesign', 3],
        '3':['', 3],
        '4':['', 4],
        '5':['', 4],
        '6':['', 4],
        '7':['', 4],
        '8':['', 4],
        '9':['', 4],
        '10':['', 4],
        '11':['', 3],
        '12':['Pictures', 3],
        '13':['wholesomememes', 3],
        '14':['Art', 3],
        '15':['CityPorn', 3],
        '16':['funny', 3],
        '17':['EarthPorn', 3],
        '18':['memes', 3],
        '19':['itookapicture', 3],
        '20':['comics', 3],
        '21':['MostBeautiful', 4],
        '22':['softwaregore', 3],
        '23':['me_irl', 3],
        '0':['DesignPorn', 3],
    }}

def subreddit_generator() -> Generator[None, str, None]:
    picture_subs = ["MostBeautiful", "itookapicture", "EarthPorn", "CityPorn", "Art", "Pictures", "DesignPorn"]
    meme_subs = ["comics", "me_irl", "funny", "wholesomememes", "ComedyCemetery", "ComedyCemetery", "softwaregore", "memes"]
    while True:
        send_order = []
        random.shuffle(picture_subs)
        random.shuffle(meme_subs)
        for i in range(max(len(picture_subs), len(meme_subs))-1):
            try:
                send_order.append(picture_subs[i])
            except:
                pass
            try:
                send_order.append(meme_subs[i])
            except:
                pass
        for subreddit in send_order:
            yield subreddit

plugin.d.subreddits = subreddit_generator()

@plugin.listener(ShardReadyEvent)
async def load_tasks(event: ShardReadyEvent):
    DailyContentChannels.set_db(plugin.bot.db)
    await Reddit.init_reddit_credentials(plugin.bot)
    trigger = IntervalTrigger(minutes=1)
    plugin.bot.scheduler.add_job(pics_of_hour, trigger)
    log.debug(plugin.bot.scheduler.running)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)


async def pics_of_hour():
    """
    sends 1x/hour images from a specific subreddit into all channels
    registered in the database
    """
    try:
        now = datetime.datetime.now()
        if now.minute != 0:
            return
        now = datetime.datetime.now()
        log.debug(now)
        # subreddit = plugin.d.daily_content["time"][str(now.hour)][0]
        subreddit = next(plugin.d.subreddits)
        if not subreddit:
            return
        tasks = []
        for mapping in await DailyContentChannels.get_all_channels(Col.CHANNEL_IDS):
            log.debug(pformat(mapping))
            for guild_id, channel_ids in mapping.items():
                for channel_id in channel_ids:
                    try:
                        task = asyncio.create_task(send_top_x_pics(subreddit, channel_id))
                        tasks.append(task)
                    except Exception:
                        await DailyContentChannels.remove_channel(Col.CHANNEL_IDS, channel_id, guild_id)
                        log.info(f"removed guild channel - was not reachable: {channel_id} from guild: {guild_id}")
        if not tasks:
            return
        _ = await asyncio.gather(*tasks)
    except Exception:
        log.critical(traceback.format_exc())

async def send_top_x_pics(subreddit: str, channel_id: int, count: int = 3):
    hours = int(tm.strftime("%H", tm.localtime()))
    try:
        posts = await Reddit.get_posts(
            subreddit=subreddit,
            top=True,
            hot=False,
            minimum=count,
            time_filter="day"
        )
        # url, title = await get_a_pic(subreddit=str(subreddit), post_to_pick=int(x), hot=False, top=True)
        if not posts:
            return
        for x in range(0, count, 1):
            embed = hikari.Embed()
            embed.title = f'{posts[x].title}'
            embed.set_image(posts[x].url)
            embed.description = f'[{posts[x].subreddit_name_prefixed}](https://www.reddit.com/{posts[x].subreddit._path})'
            log.debug(channel_id)
            await plugin.bot.rest.create_message(channel_id, embed=embed)
    except Exception as e:
        log.critical(traceback.format_exc())
        raise e
    
@plugin.listener(hikari.ReactionAddEvent)
async def on_thumb_up(event: hikari.ReactionAddEvent):
    if event.emoji_name != "👍":
        return
    
    message = await plugin.bot.rest.fetch_message(event.channel_id, event.message_id)
    if not message or not message.author.id == plugin.bot.get_me().id:
        return
    
    channel = await plugin.bot.rest.fetch_channel(event.channel_id)
    top_channels = await DailyContentChannels.get_channels_from_guild(Col.TOP_CHANNEL_IDS, channel.guild_id)
    log.debug("send to top channel")
    for ch in top_channels:
        try:
            log.debug(ch)
            await plugin.bot.rest.create_message(ch, embed=message.embeds[0])
        except Exception:
            log.error(traceback.format_exc())
            await plugin.bot.rest.create_message(event.channel_id, "I can't send this message anywhere :/")
    
         
def load(bot: Inu):
    bot.add_plugin(plugin)