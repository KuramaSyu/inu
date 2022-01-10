import random
import typing
import asyncpraw
import traceback
from typing import Union, List
import logging
import os

from dataclasses import dataclass
from asyncache import cached
from cachetools import TTLCache
from dotenv import load_dotenv
from core import Inu
from core import getLogger

# from .settings import REDDIT_APP_ID, REDDIT_APP_SECRET
REDDIT_APP_ID = None
REDDIT_APP_SECRET = None


log = getLogger(__name__)


if REDDIT_APP_ID and REDDIT_APP_SECRET:
    reddit_client = asyncpraw.Reddit(
        client_id=REDDIT_APP_ID,
        client_secret=REDDIT_APP_SECRET,
        user_agent="inu:%s:1.0" % REDDIT_APP_ID,
    )
else:
    log.error('no reddit id or secret')


class UnvalidRedditClient(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class RedditError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


# class Reddit():
#     def __init__(
#         self,
#         subreddit: str,
#         hot: bool = True,
#         top: bool = False,
#         post_to_pick: int = None,
#         minimum: int = 15,
#         time_filter: str = "day",
#     ):
#         self.subreddit = subreddit
#         self.top: bool = top
#         self.hot: bool = hot
#         self.post_to_pick: int = post_to_pick
#         self.minimum: int = minimum
#         self.reddit_client = reddit1
#         self.time_filter: str = time_filter

#         if self.top and self.hot:
#             raise RedditError("You can't filter hot and top both")
class Reddit():
    bot: Inu
    reddit_client: typing.Any
    @classmethod
    async def init_reddit_credentials(cls, bot: Inu):
        cls.bot = bot
        REDDIT_APP_ID = cls.bot.conf.REDDIT_APP_ID
        REDDIT_APP_SECRET = cls.bot.conf.REDDIT_APP_SECRET

        cls.reddit_client = asyncpraw.Reddit(
            client_id=REDDIT_APP_ID,
            client_secret=REDDIT_APP_SECRET,
            user_agent="inu:%s:1.0" % REDDIT_APP_ID,
        )

    @classmethod
    @cached(TTLCache(1024, float(3*60*60)))
    async def get_posts(
        cls,
        subreddit: str,
        hot: bool = False,
        top: bool = False,
        minimum: int = 10,
        time_filter: str = 'day',
    ) -> List[object]:

        if not cls.reddit_client:
            raise UnvalidRedditClient

        post_list = []
        try:
            subreddit = await cls.reddit_client.subreddit(subreddit)
            if hot:
                posts = subreddit.hot(limit=50)
            elif top:
                posts = subreddit.top(limit=50, time_filter=time_filter)

            async for submission in posts:
                if submission.stickied:
                    continue
                if (
                    (
                        str(submission.url).endswith('png')
                        or str(submission.url).endswith('.jpg')
                    )
                    and submission not in post_list
                ):
                    if len(post_list) >= minimum:
                        break
                    post_list.append(submission)

            return post_list

        except Exception as e:
            log.error(f'ERROR [utils/get_a_pic - exception] {e}')
            log.error(f'ERROR in utils get_a_pic - exception log {traceback.print_exc()}')
        return []


@dataclass
class RedditPost:
    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url
