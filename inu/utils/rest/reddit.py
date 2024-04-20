import random
import typing
import asyncpraw, asyncprawcore
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
    reddit_client: asyncpraw.Reddit
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
        title_filter: Optional[str] = None,
        skip_stickied: bool = True,
    ) -> List[asyncpraw.models.Submission]:
        """
        Fetch submissions with given settings. No cache implemented

        Args:
        -----
        subreddit : str
            the name of the subreddit
        hot : bool
            wether or not to search hot posts
        top : bool
            wether or not to search top posts
        minimum : int = 10
            the amount of `asyncpraw.reddit.models.Submission`s to return
        time_fileter : str = day
            the time filter to apply to the subreddit. [hour,day,week,month,year,all]
            only used with <`top`> parameter
        title_filter : Optional[str] = None
            a required name, which needs to be in the lowercase title of the post
        """
        if not cls.reddit_client:
            raise UnvalidRedditClient
        if not media_filter:
            media_filter = [""]

        post_list: List[asyncpraw.reddit.Submission] = []
        try:
            subreddit_obj: asyncpraw.reddit.Subreddit = await cls.reddit_client.subreddit(subreddit)
            if hot:
                posts = subreddit_obj.hot()
            elif top:
                posts = subreddit_obj.top(time_filter=time_filter)

            async for submission in posts:
                if minimum and len(post_list) >= minimum:
                    break
                if submission in post_list:
                    continue
                if media_filter and not Multiple.endswith_(submission.url, media_filter):
                    continue
                if skip_stickied and submission.stickied:
                    continue
                if title_filter and not title_filter.lower() in submission.title.lower():
                    continue
                post_list.append(submission)
            
            # sort post_list desc by date
            post_list.sort(key=lambda x: x.created_utc, reverse=True)
            return post_list

        except asyncprawcore.NotFound:
            raise RedditError(f"Subreddit {subreddit} not found")
        except Exception as e:
            log.error(f'ERROR [utils/get_a_pic - exception] {e}')
            log.error(f'ERROR in utils get_a_pic - exception log {traceback.print_exc()}')
        return []

    @classmethod
    @cached(TTLCache(int(2 ** 16), float(1*60*60)))
    async def get_anime_of_the_week_post(
        cls
    ) -> asyncpraw.models.Submission:
        """
        Fetches the last Submission of the Anime of the Week post

        searches the anime subreddit for the last post starting with 'top 10 anime of the week #' and png as media with 1 week timelimit
        """
        try:
            return (await cls._search(
                subreddit="anime",
                limit=10,
                media_filter=["png", "jpg"],
                time_filter="month",
                title_filter=["top 10 anime of the week #", "Anime Corner"],
                skip_stickied=False,

            ))[0]
        except IndexError:
            raise RuntimeError("Anime of the Week post not found")
    
    
    @classmethod
    async def _search(
        cls,
        subreddit: str,
        limit: int = 10,
        time_filter: str = 'day',
        media_filter: List[str] | None= ["png", "jpg"],
        title_filter: Optional[str | List[str]] = None,
        skip_stickied: bool = True,
        sort_by: str = "relevance",
    ) -> List[asyncpraw.models.Submission]:
        """
        Fetch submissions with given settings using search method. No cache implemented

        Args:
        -----
        subreddit : str
            the name of the subreddit
        minimum : int = 10
            the amount of `asyncpraw.reddit.models.Submission`s to return
        time_fileter : str = day
            the time filter to apply to the subreddit. [hour,day,week,month,year,all]
            only used with <`top`> parameter
        title_filter : Optional[str] = None
            a required name, which needs to be in the lowercase title of the post
        """


        if not cls.reddit_client:
            raise UnvalidRedditClient
        if not media_filter:
            media_filter = [""]
        if isinstance(title_filter, str):
            title_filter = [title_filter]

        post_list: List[asyncpraw.reddit.Submission] = []
        try:
            subreddit_obj: asyncpraw.reddit.Subreddit = await cls.reddit_client.subreddit(subreddit)
            posts = subreddit_obj.search(
                query=title_filter[0],
                sort="relevance",
                time_filter=time_filter,
                limit=limit,
            )

            async for submission in posts:
                if submission in post_list:
                    continue
                if media_filter and not Multiple.endswith_(submission.url, media_filter):
                    continue
                if skip_stickied and submission.stickied:
                    continue
                if (
                    title_filter 
                    and not all(f.lower() in submission.title.lower() for f in title_filter)
                ):
                    continue
                post_list.append(submission)
            
            # sort post_list desc by date
            post_list.sort(key=lambda x: x.created_utc, reverse=True)
            return post_list

        except asyncprawcore.NotFound:
            raise RedditError(f"Subreddit {subreddit} not found")
        except asyncprawcore.ResponseException as e:
            log.error(f'Reddit.search - failed with status code {e.response.status}', prefix="api")
        except Exception as e:
            log.error(f'Reddit.search - exception log {traceback.format_exception()}')
        return []
    
    @classmethod
    @cached(TTLCache(int(2 ** 16), float(1*60*60)))
    async def search(
        cls,
        subreddit: str,
        limit: int = 10,
        time_filter: str = 'day',
        media_filter: List[str] | None= ["png", "jpg"],
        title_filter: Optional[str] = None,
        skip_stickied: bool = True,
    ) -> List[asyncpraw.models.Submission]:
        """
        Fetch submissions with given settings using search method. Cache implemented

        Args:
        -----
        subreddit : str
            the name of the subreddit
        minimum : int = 10
            the amount of `asyncpraw.reddit.models.Submission`s to return
        time_fileter : str = day
            the time filter to apply to the subreddit. [hour,day,week,month,year,all]
            only used with <`top`> parameter
        title_filter : Optional[str] = None
            a required name, which needs to be in the lowercase title of the post
        """
        return await cls._search(
            subreddit=subreddit,
            limit=limit,
            time_filter=time_filter,
            media_filter=media_filter,
            title_filter=title_filter,
            skip_stickied=skip_stickied,
        )

@dataclass
class RedditPost:
    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url
