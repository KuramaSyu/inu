from datetime import datetime, timezone, timedelta

from core import Table


class TimezoneManager:

    @staticmethod
    async def fetch_timezone(guild_or_author_id: int) -> timezone:
        """
        searches db for `guild_or_author_id` and returns the timezone.
        if not found, returns UTC.

        Args:
        -----
            guild_or_author_id: `int`
                the id of the guild or the author.

        Returns:
        --------
            timezone: `datetime.timezone`
                the timezone of the guild or the author.
        """
        table = Table("guild_timezones")
        r = await table.select(["guild_or_author_id"], [guild_or_author_id])
        try:
            offset = r[0]["offset_hours"]
            return timezone(timedelta(hours=offset))
        except IndexError:
            return timezone(0)

    @staticmethod
    async def set_timezone(guild_or_author_id: int, offset_hours: int):
        table = Table("guild_timezones")
        await table.upsert(
            ["guild_or_author_id", "offset_hours"], 
            [guild_or_author_id, offset_hours]
        )

    

    