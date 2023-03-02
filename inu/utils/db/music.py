import datetime
from typing import *

from cachetools import TTLCache
from asyncache import cached

from core import Table, getLogger


log = getLogger(__name__)



class MusicHistoryHandler:
    """A class which handles music history stuff and syncs it with postgresql"""
    max_length: int = 200  # max length of music history list¡
    table = Table("music_history")

    @classmethod
    async def add(cls, guild_id: int, title: str, url: str):
        await cls.table.insert(
            ["title", "url", "played_on", "guild_id"], 
            [title, url, datetime.datetime.now(), guild_id]
        )

    @classmethod
    async def get(cls, guild_id: int) -> List[Dict[str, Any]]:
        """
        Get last played titles in <guild_id>

        Args:
        -----
        `guild_id : int`
            the guild_id you want tracks from

        Returns:
        --------
        `List[Dict[str, Any]] :`
            a list with all the records in DESC order.
            keys: `title`, `url`
        """
        records = await cls.table.fetch(
            f"SELECT * FROM {cls.table.name} WHERE guild_id = $1 ORDER BY played_on DESC LIMIT {cls.max_length}", 
            guild_id
        )
        return records or []
    
    @classmethod
    @cached(TTLCache(1024, 30))
    async def cached_get(cls, guild_id: int) -> List[Dict[str, Any]]:
        """
        Get last played titles in <guild_id> with a 30s cache

        Args:
        -----
        `guild_id : int`
            the guild_id you want tracks from

        Returns:
        --------
        `List[Dict[str, Any]] :`
            a list with all the records in DESC order.
            keys: `title`, `url`
        """
        return await cls.table.fetch(
            f"SELECT title, url FROM {cls.table.name} WHERE guild_id = $1 ORDER BY played_on DESC LIMIT {cls.max_length}", 
            guild_id
        )

    @classmethod
    async def clean(cls, max_age: datetime.timedelta = datetime.timedelta(days=90)):
        del_oder_than = datetime.datetime.now() - max_age
        deleted = await cls.table.execute(f"DELETE FROM {cls.table.name} WHERE played_on < $1", del_oder_than)
        if deleted:
            log.info(f"Cleaned {len(deleted)} music history entries")