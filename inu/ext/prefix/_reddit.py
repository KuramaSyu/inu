import asyncio
import typing
from typing import (
    List,
    Dict,
    Any,
    Optional,
    Union
)
import time as tm
import random
import logging

import asyncpraw
import hikari
import lightbulb
from lightbulb import Context

from utils.reddit import Reddit

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class images(lightbulb.Plugin):
    def __init__(self, bot: lightbulb.Bot):
        super().__init__()
        self.bot = bot

            
        self.last_subreddits = {
            'name_subreddit':{
            'list':'list_of_urls',
            'expire_time':'time + 30 min'},
        }
        self.last_update_hentai = 0
        self.updating_hentai = False
        


    @lightbulb.command(aliases = ['rand_pic', 'picture'])
    async def pic(self, ctx: Context, subreddit: str = ""):
        '''
        Sends a nice Picture
        Parameters:
        [Optional] subreddit: The subreddit u want a picture from - Default: A list of picture Subreddits
        '''
        if subreddit == '':
            subreddit = random.choice(['itookapicture','CityPorn','EarthPorn', 'Pictures'])
        await self.send_pic(ctx, subreddit)


    @lightbulb.command(aliases = ['meme'])
    async def memes(self, ctx: Context, subreddit: str = ''):
        '''
        Sends a meme
        Parameters:
        [Optional] subreddit: The subreddit u want a picture from - Default: A list of meme Subreddits
        '''
        if subreddit == '':
            subreddit = random.choice(['memes','funny'])
        await self.send_pic(ctx, subreddit)



    @lightbulb.command()
    async def hentai(self, ctx: Context, subreddit: str = None):
        '''
        Sends a Hentai picture
        Parameters:
        [Optional] subreddit: The subreddit u want a picture from - Default: A list of Hentai Subreddits
        '''
        amount = 5
        subreddits = []
        if (
            self.last_update_hentai - float(3*60*60) - 120 < tm.time() 
            and not self.updating_hentai
        ):
            amount = 1
        if not subreddit:
            subreddit = random.choice(
                (subreddits := [
                    'animearmpits', 'AnimeBooty',
                    'animelegs', 'Atago', 'bluehairhentai', 'chiisaihentai', 'ecchi',
                    'hentai', 'HentaiBlowjob', 'HentaiCumsluts', 'HentaiSchoolGirls',
                    'MasturbationHentai', 'Nekomimi', 'Sukebei', 'thighdeology', 'WaifusOnCouch',
                ])
            )
        await self.send_pic(ctx, subreddit, footer=False, amount=amount)
        if self.last_update_hentai + float(3*60*60) < tm.time() and subreddits:
            self.last_update_hentai = float(tm.time()) + float(3*60*60)
            await self._update_pictures(subreddits=subreddits)
        #await self.send_pic(ctx, subreddit, footer=False)

    async def _update_pictures(self, subreddits: List[str]):
        self.updating_hentai = False
        async def update(subreddit):
            _ = await Reddit.get_posts(
                subreddit=subreddit,
                hot=True,
                minimum=5,
            )
        tasks: List[asyncio.Task] = []
        for subreddit in subreddits:
            asyncio.create_task(update(subreddit))
        L = await asyncio.gather(*tasks)
        self.updating_hentai = True
        log.debug("finished caching hentai urls")
        

    async def send_pic(self, ctx: Context, subreddit: str, footer: bool = True, amount: int= 5):
        posts = await Reddit.get_posts(
            subreddit=subreddit,
            hot=True,
            minimum=amount,
        )
        post = random.choice(posts)
        embed = hikari.Embed()
        embed.title = post.title
        embed.set_image(post.url)
        if footer:
            embed.set_footer(text=f"r/{subreddit}")
        await ctx.respond(embed=embed)


def load(bot: lightbulb.Bot):
    bot.add_plugin(images(bot))

