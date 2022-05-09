from datetime import datetime, timedelta, timezone, tzinfo
import pytz

def is_dst(dt=None, timezone='Europe/Berlin'):
    timezone = pytz.timezone(timezone)
    if dt is None:
        dt = datetime.datetime.now(datetime.timezone.utc)
    if dt.tzinfo is None:
        tz_aware_dt = timezone.localize(dt, is_dst=None)
    else:
        tz_aware_dt = dt.astimezone(timezone)
    return tz_aware_dt.tzinfo._dst.seconds != 0

def dst(dt=None, timezone='Europe/Berlin') -> int:
    """Returns the DST offset in seconds"""
    timezone = pytz.timezone(timezone)
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        tz_aware_dt = timezone.localize(dt, is_dst=None)
    else:
        tz_aware_dt = dt.astimezone(timezone)
    return tz_aware_dt.tzinfo._dst.seconds


print(dst(datetime(2020, 3, 1)))