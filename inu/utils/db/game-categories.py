from datetime import datetime
from typing import *

from core import Database, Table


class GameCategories:
    db: Database
    
    @classmethod
    def set_db(cls, db: Database):
        cls.db = db

    @classmethod
    async def fetch_guilds(cls) -> List[int]:
        ...

    @classmethod
    async def add(
        cls,
        guild_id: int,
        game: str,
    ):
        """inserts guild_id and game into database. Timestamp will be time of method call"""
        ...

    @classmethod
    async def delete(when_older_than: datetime):
        """deletes all records which are older than <`when_older_than`>"""
        ...

    @classmethod
    async def fetch_games(cls, guild_id: int, since: datetime) -> Dict[str, int]:
        """
        Args:
            guild_id (int): /

        Returns:
            Dict[str, int]: Mapping from game name to the time in minutes played it
        """
        ...


