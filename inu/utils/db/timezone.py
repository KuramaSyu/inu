from datetime import datetime, timezone, timedelta
from typing import *

import pytz

from core import Table


class TimezoneManager:

    @staticmethod
    def dst(dt: Optional[datetime] = None, tz: str = "Europe/Berlin") -> int:
        """Returns the DST offset in seconds"""
        timezone = pytz.timezone(tz)
        # if dt is None:
        dt = datetime.now(timezone)
        td = dt.tzinfo.dst(dt)
        if not isinstance(td, timedelta):
            return 0
        else:
            return int(td.total_seconds())
        # if dt.tzinfo is None:
        #     tz_aware_dt = timezone.localize(dt, is_dst=None)
        # else:
        #     tz_aware_dt = dt.astimezone(timezone)
        # return tz_aware_dt.tzinfo._dst.seconds

    @classmethod
    def is_dst(cls, dt=None, timezone='Europe/Berlin'):
        """Whether the given datetime is in DST"""
        return (cls.dst(dt, timezone) != 0)

    @classmethod
    async def fetch_timezone(cls, guild_or_author_id: int) -> timezone:
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
            td = timedelta(hours=offset)
        except IndexError:
            td = timedelta(hours=0)
        finally:
            if cls.is_dst():
                td += timedelta(hours=1)
            return timezone(td)

    @classmethod
    async def set_timezone(cls, guild_or_author_id: int, offset_hours: int):
        """
        set a timezone for a guild or author.

        Args:
        -----
        guild_or_author_id: `int`
            the id of the guild or the author.
        offset_hours: `int`
            the offset in hours.

        Returns:
        --------
            None
        """
        table = Table("guild_timezones")
        if cls.is_dst():
            offset_hours -= 1
        await table.upsert(
            ["guild_or_author_id", "offset_hours"], 
            [guild_or_author_id, offset_hours]
        )

    

    