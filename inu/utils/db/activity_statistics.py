from datetime import datetime, timedelta
from typing import *
import pickle
import pandas as pd
#from dataenforce import Dataset

from core import Database, Table


# how many minutes does python takes the records?
# which is the value in minutes for user_amount = 1?
USER_AMOUNT_TO_MINUTES = 10


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
        -----
        guild_id: int

        Returns:
        --------
        Dict[str, int]: 
            Mapping from game name to the time in minutes played it
        """
        ...


class Games:
    PROGRAMMING = ["Visual Studio Code", "Visual Studio", "Sublime Text", "Atom", "VSCode", "Webflow", "Code"]
    MUSIC = ["Spotify", "Google Play Music", "Apple Music", "iTunes", "YouTube Music"]
    DUPLEX_GAMES = ["Rainbow Six Siege", "PUBG: BATTLEGROUNDS"]  # these will be removed from games too


class CurrentGamesManager:

    @classmethod
    async def add(
        cls,
        guild_id: int,
        game: str,
        amount: int,
    ) -> Optional[Mapping[str, Any]]:
        """inserts guild_id and game into database. Timestamp will be time of method call"""
        table = Table("current_games", error_log=False)
        now = datetime.now()
        about_now = datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            hour=now.hour,
            minute=now.minute,
        )
        return await table.insert(
            which_columns=["guild_id", "game", "user_amount", "timestamp"],
            values=[guild_id, game, amount, about_now],
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
    async def fetch_games(
        cls, 
        guild_id: int, 
        since: datetime
    ) ->Optional[List[Mapping[str, Any]]]:
        """
        Args:
        -----
        guild_id: int
        

        Returns:
        --------
        Dict[str, int]: 
            Mapping from game name to the time in minutes played it
        """
        table = Table("current_games")
        sql = (
            f"SELECT game, SUM(user_amount) AS amount, MIN(timestamp) AS first_occurrence\n"
            f"FROM {table.name}\n"
            f"WHERE guild_id = $1 AND timestamp > $2\n"
            f"GROUP BY game"
        )
        return await table.fetch(sql, guild_id, since)

    @classmethod
    async def fetch_raw_activities(
        cls, 
        guild_id: int, 
        since: datetime
    ) -> Optional[List[Mapping[str, Any]]]:
        """
        Args:
        -----
        guild_id: int

        Returns:
        --------
        Dict[str, int]: 
            Mapping from game name to the time in minutes/10 played it
        """
        table = Table("current_games")
        sql = (
            f"SELECT game, user_amount, timestamp\n"
            f"FROM {table.name}\n"
            f"WHERE guild_id = $1 AND timestamp > $2"
        )
        return await table.fetch(sql, guild_id, since)

    @classmethod
    async def fetch_total_activity_by_timestamp(
        cls, 
        guild_id: int, 
        since: datetime,
    ) -> List[Mapping[str, Any]]:
        """
        Args:
        -----
        guild_id: int

        Returns:
        --------
        Dict[datetime, int]: 
            Mapping from timestamp to amount of users total application activity
        """
        table = Table("current_games")
        sql = (
            f"SELECT ts_round(timestamp, 300) AS round_timestamp, SUM(user_amount) AS total_user_amount\n"
            f"FROM {table.name}\n"
            f"WHERE guild_id = $1 AND timestamp > $2\n"
            f"GROUP BY round_timestamp\n"
            f"ORDER BY round_timestamp"
        )
        return await table.fetch(sql, guild_id, since)

    @classmethod
    async def fetch_activity_from_application(
        cls,
        guild_id: int,
        application_name: str,
        since: datetime,
    ):
        """

        Parameters
        ----------
        guild_id : int
            the id of the guild
        application_name : str
            the name of the applicaiton
        since : datetime
            the time since which the activity should be fetched

        Returns:
        --------
        Dict[datetime, int]:
            Mapping from timestamp to amount of users total application activity
        """
        table = Table("current_games")
        table.return_as_dataframe(True)
        sql = (
            f"SELECT ts_round(timestamp, 300) AS round_timestamp, SUM(user_amount) AS total_user_amount\n"
            f"FROM {table.name}\n"
            f"WHERE guild_id = $1 AND timestamp > $2 AND game = $3\n"
            f"GROUP BY round_timestamp\n"
            f"ORDER BY round_timestamp"
        )
        return await table.fetch(sql, guild_id, since, application_name)

    @classmethod
    async def fetch_activities(
        cls,
        guild_id: int,
        since: datetime,
        activity_filter: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        fetches activies from a guild

        Args:
        -----
        guild_id: int
        since: datetime
            timepoint where return data starts
        activity_filter: List[str]
            list of activities to filter by (only list element will be returned)

        Returns:
        --------
        List[Mapping[str, Any]]:
            List with all reocrds from a guild.
            These records will have a timestamp, game and hours.
            The records are taken every 10 minutes.
            Keys of Mapping:
                r_timestamp: datetime
                    rounded timestamp
                game: str
                    name of the game
                hours: int
                    amount of hours played

        """
        table = Table("current_games")
        table.return_as_dataframe(True)
        additional_activity_filter = f"AND game = ANY($3)" if activity_filter else ""
        optional_arg = [activity_filter] if activity_filter else []
        # ts_round(timestamp, 300) -> round timestamp to nearest 10 minutes
        sql = ( 
            f"SELECT ts_round(timestamp, 300) AS r_timestamp, game, CAST(user_amount AS FLOAT)*{USER_AMOUNT_TO_MINUTES}/60 AS hours\n"
            f"FROM {table.name}\n"
            f"WHERE guild_id = $1 AND timestamp > $2 {additional_activity_filter}\n"
        )
        return await table.fetch(sql, guild_id, since, *optional_arg)

    @classmethod
    async def fetch_top_games(
        cls,
        guild_id: int,
        since: datetime,    
        limit: int = 15,
        remove_activities: List[str] = [],
    ) -> List[Dict[str, int]]:
        """
        Args:
        -----
        guild_id: int
        since: datetime
            timepoint where return data starts
        limit: int
            the amount of games to return

        Returns:
        --------
        List[Dict[str, int]]:
            List with Mappings from game name to the time in minutes/10 played it

        Note:
        -----
        The games are sorted by the amount (minutes/10) played.
        """
        table = Table("current_games")
        additional_filter = f"AND game != ALL($4)" if remove_activities else ""
        optional_arg = [remove_activities] if remove_activities else []
        sql = (
            f"SELECT game, SUM(user_amount) AS amount\n"
            f"FROM {table.name}\n"
            f"WHERE guild_id = $1 AND timestamp > $2 {additional_filter}\n"
            f"GROUP BY game\n"
            f"ORDER BY amount DESC\n"
            f"LIMIT $3"
        )
        records = await table.fetch(sql, guild_id, since, limit, *optional_arg)
        return [{r["game"]: r["amount"]} for r in records]

    @classmethod
    async def fetch_total_activity_per_day(
        cls, 
        guild_id: int, 
        since: datetime,
        ignore_activities: List[str] = [],
    ) -> pd.DataFrame:
        """Returns the total amount of played hours per day since <`since`> from <`guild_id`>

        Args:
        -----
        guild_id: int
        since: datetime

        Returns:
        --------
        pd.Dataframe:
            Keys:
            - date: datetime
            - hours: int
        """

        additional_filter = f"AND game != ALL($3)" if ignore_activities else ""
        additional_args = [ignore_activities] if ignore_activities else []
        sql = f"""
        SELECT date_trunc('day', timestamp)::TIMESTAMP WITH TIME ZONE AS datetime, SUM(user_amount)/6 AS hours\n
        FROM current_games\n
        WHERE guild_id = $1 AND timestamp > $2 {additional_filter}\n
        GROUP BY datetime \n
        ORDER BY datetime ASC
        """
        table = Table("current_games")
        table.return_as_dataframe(True)
        return await table.fetch(sql, guild_id, since, *additional_args)

