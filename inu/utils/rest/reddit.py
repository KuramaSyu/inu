import random
import typing
import asyncpraw
import traceback
from typing import *
import logging
import os

from dataclasses import dataclass
from asyncache import cached
from cachetools import TTLCache
from dotenv import load_dotenv
from core import Inu
from core import getLogger
from utils import Multiple


log = getLogger(__name__)


class UnvalidRedditClient(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class RedditError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class Reddit():
    bot: Inu
    reddit_client: typing.Any
    @classmethod
    async def init_reddit_credentials(cls, bot: Inu):
        cls.bot = bot
        REDDIT_APP_ID = cls.bot.conf.reddit.ID
        REDDIT_APP_SECRET = cls.bot.conf.reddit.SECRET

        cls.reddit_client = asyncpraw.Reddit(
            client_id=REDDIT_APP_ID,
            client_secret=REDDIT_APP_SECRET,
            user_agent="inu:%s:1.0" % REDDIT_APP_ID,
        )
    @classmethod
    @cached(TTLCache(int(2 ** 16), float(3*60*60)))
    async def get_posts(
        cls,
        subreddit: str,
        hot: bool = False,
        top: bool = False,
        minimum: int = 10,
        time_filter: str = 'day',
        media_filter: List[str] = ["png", "jpg"]
    ) -> List[asyncpraw.models.Submission]:
        """
        Fetches submissions for specified settings.

        Args:
        -----
        subreddit : str
            the subreddit you want posts from
        hot : bool
            wether or not to fetch posts under `hot`
        top : bool
            wether or not to fetch posts under `top`
        minimum : int
            the amount of posts to fetch
        time_filter : str
            the time filter to use for hot posts. Only if hot is True.
            Possible options:
                - day
                - week
                - month
                - year
        Note:
        -----
        submissions will be cached for 3 hours
        """
        return await cls._fetch_posts(
            subreddit,
            hot,
            top,
            minimum,
            time_filter,
            media_filter,
        )

    @classmethod
    async def _fetch_posts(
        cls,
        subreddit: str,
        hot: bool = False,
        top: bool = False,
        minimum: int = 10,
        time_filter: str = 'day',
        media_filter: List[str] | None= ["png", "jpg"],
    ) -> List[asyncpraw.models.Submission]:
        """
        Fetch submissions with given settings. No cache implemented
        """
        if not cls.reddit_client:
            raise UnvalidRedditClient
        if not media_filter:
            media_filter = [""]

        post_list: List[asyncpraw.models.Submission] = []
        try:
            subreddit = await cls.reddit_client.subreddit(subreddit)
            if hot:
                posts = subreddit.hot()
            elif top:
                posts = subreddit.top(time_filter=time_filter)

            async for submission in posts:
                if submission.stickied:
                    continue
                if (
                    Multiple.endswith_(submission.url, media_filter)
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
