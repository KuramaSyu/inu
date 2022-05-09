from datetime import datetime, timedelta, timezone, tzinfo
import pytz


def dst(dt=None, tz: str = "Europe/Berlin") -> int:
    """Returns the DST offset in seconds"""
    timezone = pytz.timezone(tz)
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        tz_aware_dt = timezone.localize(dt, is_dst=None)
    else:
        tz_aware_dt = dt.astimezone(timezone)
    return tz_aware_dt.tzinfo._dst.seconds

def is_dst(dt=None, timezone='Europe/Berlin'):
    return (dst(dt, timezone) != 0)

print(is_dst(dt=datetime(2020, 6, 1)))