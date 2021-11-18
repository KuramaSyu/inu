import asyncio
import typing
from typing import (
    Dict,
    Union,
    Optional,
    List,
)
import random
import datetime
import time as tm
import traceback
import logging

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


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class DailyPosts(Plugin):
    def __init__(self, bot: Inu):
        super().__init__()
        self.bot: Inu = bot
        self.daily_content = {
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
                '23':['bonehurtingjuice', 3],
                '0':['DesignPorn', 3],
            }}

        
    @lightbulb.listener(ShardReadyEvent)
    async def load_tasks(self, event: ShardReadyEvent):
        DailyContentChannels.set_db(self.bot.db)
        await Reddit.init_reddit_credentials(self.bot)
        trigger = IntervalTrigger(seconds=10)
        self.bot.scheduler.add_job(self.pics_of_hour, trigger)
        log.debug(self.bot.scheduler.running)
        self.bot.scheduler.print_jobs()


    async def pics_of_hour(self):
        """
        sends 1x/hour images from a specific subreddit into all channels
        registered in the database
        """
        try:
            log.debug("started task")
            # now = datetime.datetime.now()
            # if now.minute != 0:
            #     return
            now = datetime.datetime.now()
            log.debug(now)
            subreddit = None
            for key, value in self.daily_content["time"].items():
                subreddit, hour = value[0], value[1]
                if int(hour) != now.hour:
                    continue
                if subreddit == '':
                    return
                else:
                    break
            if subreddit is None:
                return
            tasks = []
            for channel_id in await DailyContentChannels.get_all_channels():
                asyncio.create_task(self.send_top_x_pics(subreddit, channel_id))
            if not tasks:
                log.debug("No channel to send pictures to")
                return
            await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
            log.debug("sent pictures in all channels")
        except Exception:
            log.critical(traceback.format_exc())

    async def send_top_x_pics(self, subreddit: str, channel_id: int, count: int = 5):
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
                if x == int(count - 1):
                    embed.set_footer(text=f'r/{subreddit}  |  {hours}:00')
                log.debug(channel_id)
                try:
                    await self.bot.rest.create_message(channel_id, embed=embed)
                except hikari.NotFoundError:
                    log.info(f"deleting channel_id: {channel_id}")
                    channel = self.bot.rest.fetch_channel(channel_id)
                    await DailyContentChannels.remove_channel(channel_id, channel.guild.id)
        except Exception:
            log.critical(traceback.format_exc())
            
def load(bot: Inu):
    bot.add_plugin(DailyPosts(bot))