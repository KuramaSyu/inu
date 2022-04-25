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
    async def delete(cls, when_older_than: datetime):
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

class CurrentGamesManager:

    @classmethod
    async def add(
        cls,
        guild_id: int,
        game: str,
        amount: int,
    ) -> Optional[Mapping[str, Any]]:
        """inserts guild_id and game into database. Timestamp will be time of method call"""
        table = Table("current_games")
        return await table.insert(
            which_columns=["guild_id", "game", "user_amount", "timestamp"],
            values=[guild_id, game, amount, datetime.now()],
        )

    @classmethod
    async def delete(cls, when_older_than: datetime) -> Optional[List[Mapping[str, Any]]]:
        """deletes all records which are older than <`when_older_than`>"""
        table = Table("current_games")
        sql = (
            f"DELETE FROM {table.name}\n"
            f"WHERE timestamp < $1"
        )
        return await table.fetch(sql, when_older_than)

    @classmethod
    async def fetch_games(cls, guild_id: int, since: datetime) ->Optional[List[Mapping[str, Any]]]:
        """
        Args:
            guild_id (int): /

        Returns:
            Dict[str, int]: Mapping from game name to the time in minutes played it
        """
        table = Table("current_games")
        sql = (
            f"SELECT game, SUM(user_amount) AS amount\n"
            f"FROM {table.name}\n"
            f"WHERE guild_id = $1 AND timestamp > $2\n"
            f"GROUP BY game"
        )
        return await table.fetch(sql, guild_id, since)

