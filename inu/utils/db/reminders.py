import traceback
from typing import *
import json
import logging
import datetime
from datetime import timedelta, timezone
import asyncio
from enum import Enum
import time
import re

import hikari
from hikari.impl import MessageActionRowBuilder
from hikari.embeds import Embed
import lightbulb
from lightbulb.context import Context
import asyncpg
import mock

from core.bot import Inu
from core import Database, Table
from ..string_crumbler import PeekIterator, NumberWordIterator

from core import getLogger

log = getLogger(__name__)


# the time in seconds, after the next sql statement, to get further reminders, will be executed
REMINDER_UPDATE = 5*60


def get_seconds_until_next(weekday: int) -> int:
    now = datetime.datetime.now()
    start_of_day = datetime.datetime(year=now.year, month=now.month, day=now.day, minute=1)
    weekday_n = now.weekday()
    i = weekday_n
    
    for x in range(1, 8):
        y = (x + i) % 7
        if y == weekday:
            fut_day = start_of_day + timedelta(days=x)
            return int(fut_day.timestamp() - now.timestamp())
    return 0

class TimeUnits(Enum):
    """
    Enum, which represents time units
    """



    second = {
        "aliases": ["second", "s", "sec", "seconds"],
        "in_seconds": 1,
    }
    millisecond = {
        "aliases": ["millisecond", "ms", "milliseconds"],
        "in_seconds": second["in_seconds"] / 1000,
    }

    nanosecond = {
        "aliases": ["nanosecond", "ns", "nanoseconds"],
        "in_seconds": millisecond["in_seconds"] / 1000000,
    }

    minute = {
        "aliases": ["minute", "min", "m", "minutes"],
        "in_seconds": second["in_seconds"] * 60,  
    }
    hour = {
        "aliases": ["hour", "h", "hours"],
        "in_seconds": minute["in_seconds"] * 60,  
    }
    day = {
        "aliases": ["day", "d", "days"],
        "in_seconds": hour["in_seconds"] * 24,  
    }
    week = {
        "aliases": ["week", "w", "weeks"],
        "in_seconds": day["in_seconds"] * 7,  
    }
    month = {
        "aliases": ["month", "m", "months"],
        "in_seconds": day["in_seconds"] * 30,  
    }
    year = {
        "aliases": ["year", "y", "years"],
        "in_seconds": day["in_seconds"] * 365,  
    }
    pizza = {
        "aliases": ["pizza", "pizzas"],
        "in_seconds": minute["in_seconds"] * 15,  
    }
    monday = {
        "aliases": {"monday", "mon"},
        "in_seconds": get_seconds_until_next(0),
        "d": 0
    }
    tuesday = {
        "aliases": {"tuesday", "tue"},
        "in_seconds": get_seconds_until_next(1),
        "d": 1
    }
    wednesday = {
        "aliases": {"wednesday", "wed"},
        "in_seconds": get_seconds_until_next(2),
        "d": 2
    } 
    thursday = {
        "aliases": {"thursday", "thu"},
        "in_seconds": get_seconds_until_next(3),
        "d": 3
    }
    friday = {
        "aliases": {"friday", "fri"},
        "in_seconds": get_seconds_until_next(4),
        "d": 4
    }
    saturday = {
        "aliases": {"saturday", "sat"},
        "in_seconds": get_seconds_until_next(5),
        "d": 5
    }
    sunday = {
        "aliases": {"sunday", "sun"},
        "in_seconds": get_seconds_until_next(6),
        "d": 6,
    }
        


class TimeConverter:
    @classmethod
    def is_parable(cls, query: str) -> bool:
        pass

    @classmethod
    def to_seconds(cls, unit: dict, amount: Union[int, float]) -> float:
        """
        Returns:
        --------
            - (float) the given time unit and it's ammount in seconds
        """
        if unit.value.get("d"):
            unit.value["in_seconds"] = get_seconds_until_next(unit.value.get("d"))
        log.debug(f"{unit=};{float(unit.value['in_seconds'])}")
        return float(unit.value["in_seconds"] * amount)

    @classmethod
    def all_aliases(cls) -> List[str]:
        """
        Returns:
        --------
            - (list) all names and aliases of all time units of class `TimeUnits`
        """
        return [alias for unit in [unit.value for unit in TimeUnits] for alias in unit["aliases"]]

    @classmethod
    def get_unit(cls, str_unit: str) -> Optional[TimeUnits]:
        """
        Returns:
        --------
            - (str | None) the given str as unit, if there is a unit with this name/alias, otherwise `None`
        """
        for unit in TimeUnits.__members__.values():
            if str_unit in unit.value["aliases"]:
                return unit



    @classmethod
    def time_to_seconds(cls, time: List) -> int:
        """
        Args:
        -----
            - time: (List) a list with minutes (index 0) and seconds (index 1)
        Returns:
        --------
            - (int) the given time in seconds 
        """
        return int(cls.hour.value["in_seconds"]*time[0], cls.minute.value["in_seconds"]*time[1])


class TimeParser:
    def __init__(self, query: str, offset_hours: int):

        self.log = getLogger(__name__, self.__class__.__name__)

        self.query = query
        self.in_seconds: float = 0
        self.matches: Dict[TimeUnits, float] = {}

        self.tz = timezone(offset=timedelta(hours=offset_hours))
        self._now: datetime.datetime = datetime.datetime.now(tz=self.tz)

        self.unresolved = []
        self.unused_query = ""
        self.parse()
        self.is_interpreted = False

    @property
    def now(self):
        return self._now + timedelta(seconds=self.in_seconds)


    def parse(self):
        """
        parses the query to wait time in seconds and unused query (the remind text).
        Tries to pare relative time, and after that (if there was no relative time)
        it tries to pare datetime
        """
        self.log.debug(0, self.query)
        parse_end_indexes = []
        i1 = self.parse_relative_time(self.query)
        parse_end_indexes.append(i1)
        self.log.debug(f"1, {i1}, {self.query[i1:]}")

        i2 = self.parse_time(self.query)
        if i2 != -1:
            self.log.debug(f"2, {i2}, {self.query[i2:]}")
            parse_end_indexes.append(i2)
            i3 = self.parse_relative_time(self.query[i2:])
            i3 += i2
            parse_end_indexes.append(i3)
            self.log.debug(f"3, {i3}, {self.query[i3:]}")
        i4 = self.parse_date(self.query)
        if i4 != -1:
            self.log.debug(f"4, {i4}, {self.query[i4:]}")
            parse_end_indexes.append(i4)
            i5 = self.parse_relative_time(self.query[i4:])
            i5 += i4
            parse_end_indexes.append(i5)
            self.log.debug(f"5, {i5}, {self.query[i5:]}")

        unesed_query_start = max(parse_end_indexes)
        if unesed_query_start != -1:
            self.unused_query = self.query[unesed_query_start:]
    
    def parse_time(self, mut_query: str):
        """
        - Adds the timediff (seconds) as timestamp to `self.in_seconds`
        - Changes `self.unused_query`
        """
        # endtime HH:MM 24h
        # (HH, MM, "AM"|"PM"|"")
        raw_str = ""
        time = []
        if not time:
            # HH:MM 12-hour format, optional leading 0, mandatory meridiems (AM/PM)
            regex_hh_mm_12 = r"(([0-9]|0[0-9]|1[0-2]):([0-5][0-9])[ ]?([AaPp][Mm]){1,1})"
            time_list = re.findall(regex_hh_mm_12, self.query)
            if time_list:
                time_ = time_list[0]
                add = 12 if time_[3] == "pm" else 0  #am, pm ""
                time = [int(time_[1])+add, int(time_[2]), time_[3].upper()]
                raw_str = time_[0]
        if not time:
            #HH:MM 24-hour with leading 0
            regex_hh_mm_24 = r"(([0-9]|0[0-9]|1[0-9]|2[0-4]):([0-5][0-9]))"
            time_list = re.findall(regex_hh_mm_24, self.query)
            if time_list:
                time_ = time_list[0]
                time = [int(time_[1]), int(time_[2]), ""] #HH, MM
                raw_str = time_[0]
        if not time:
            # HH am/pm 12-hour format, optional leading 0
            regex_hh_mm_12 = r"(([0-9]|0[0-9]|1[0-2])[ ]?([AaPp][Mm]){1,1})"
            time_list = re.findall(regex_hh_mm_12, self.query)
            if time_list:
                time_ = time_list[0]
                log.debug(time_)
                add = 12 if time_[2] == "pm" else 0
                time = [int(time_[1])+add, 0, time_[2].upper()]
                raw_str = time_[0]
        if time:
            if time[0] == 24:
                time[0] = 0
        else:
            return -1

        now = self.now
        alert = datetime.datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            hour=int(time[0]),
            minute=int(time[1]),
            tzinfo=self.tz,
        )
        while alert < now:
            t = datetime.timedelta(hours=12)
            if time[2] in ["AM", "PM"]:
                self.is_interpreted = True
                t = datetime.timedelta(hours=24)
            alert += t
        self.in_seconds += float(alert.timestamp() - now.timestamp())
        self.unused_query = self.unused_query.replace(str(raw_str), "")
        # for mut_query
        i = mut_query.find(time_[0])
        if i != -1:
            i += len(time_[0])
        return i

    def parse_date(self, query: str):
        indexes = []
        regex = r"(([12]\d{3})[/.-](0[1-9]|1[0-2])[/.-](0[1-9]|[12]\d|3[01]))"
        dates = re.findall(regex, query)
        if not dates:
            return -1
        now = self.now
        for date in dates:
            alert = datetime.datetime(
                year=int(date[1]),
                month=int(date[2]),
                day=int(date[3]),
                tzinfo=self.tz,
            )
            self.in_seconds += alert.timestamp() - now.timestamp()
            indexes.append(self.query.find(date[0])+len(date[0]))
        return max(indexes)
        

    def parse_relative_time(self, query: str) -> int:
        """
        Returns
        -------
            - (int) the index, where the parser has stopped to parse
        """
        gen = NumberWordIterator(query)
        str_unit = ""
        amount: float = None
        matches = {}
        is_changed = False
        parse_end_index = -1
        type_ = None
        # iterate through query. each iteration is a float or a str.
        # if its a float, it will be stored as amount
        # if its a str, its will be stored as the unit
        # -> converting str to a unit
        # actual add (unit to seconds) * amount (by default 1) to total waiting seconds 
        for item in gen:
            if item == "":
                continue
            if type(item) == type_:
                break
            type_ = type(item)
            if isinstance(item, float):
                amount = item
            else:
                if item.endswith(",") or item.endswith(";"):
                    item = item[:-1]
                str_unit = item
            if (str_unit) and (amount is None):
                amount = 1
            if str_unit and amount:
                if matches.get(str_unit):
                    matches[str_unit] += amount
                else:
                    matches[str_unit] = amount

                unit = TimeConverter.get_unit(str_unit)
                if not unit:
                    self.unresolved.append([str_unit, amount])
                    if is_changed:
                        parse_end_index = gen.last_word_index-1
                    break
                is_changed = True
                self.in_seconds += TimeConverter.to_seconds(unit, amount)
                if self.matches.get(unit.name):
                    self.matches[unit.name] += amount
                else:
                    self.matches[unit.name] = amount

                str_unit = ""
                amount = None
                type_ = None

        if parse_end_index == -1 and is_changed:
            parse_end_index = gen.index
        return parse_end_index

class BaseReminder:
    def __init__(self, query: str, hour_offset: int = 0):
        self._query = query
        self.hour_offset = hour_offset
        if self._query:
            self.time_parser = TimeParser(self._query, hour_offset)
            self.remind_text = self.time_parser.unused_query
            self.in_seconds = self.time_parser.in_seconds
            self.wait_until: float = time.time() + self.in_seconds
            self.datetime: datetime.datetime = datetime.datetime.fromtimestamp(self.wait_until)
        else:
            self.time_parser = None
            self.remind_text = None
            self.in_seconds = None
            self.wait_until = None
            self.datetime = None
        self.id: Optional[int] = None

    @property
    def remaining_time(self) -> float:
        """
        Returns:
        --------
            - (int) the remaing time in seconds
        """
        return self.wait_until - time.time()


class HikariReminder(BaseReminder):
    def __init__(
        self,
        channel_id: int,
        creator_id: int,
        message_id: int = 0,
        query: Optional[str] = None,
        ctx: Context = None,
        offset_hours: int = 0,
    ):
        self.ctx = ctx
        super().__init__(query=query, hour_offset=offset_hours)
        self.message_id = message_id
        self.channel_id = channel_id
        self.creator_id = creator_id
        
        self.bot: Inu = Reminders.bot

        if self._query:
            if self.in_seconds >= Reminders.REMINDER_UPDATE:
                loop = asyncio.get_event_loop()
                asyncio.Task(self.store_reminder(), loop=loop)
            else:
                asyncio.Task(self.schedule())
    


    @property
    def guild_id(self) -> Optional[int]:
        ch = Reminders.bot.cache.get_guild_channel(self.channel_id)
        if not ch:
            return None
        return ch.guild_id

    async def store_reminder(self):
        self.id = await Reminders.add_reminder(self)

    async def schedule(self):
        await asyncio.sleep(self.remaining_time)
        await self.destroy_reminder()
        await self.send_message()

    async def send_message(self):
        snooze_times = {
            "5 min": 5*60, "10 min": 10*60, "15 min": 15*60, "20 min": 20*60, 
            "30 min": 30*60, "1 hour": 60*60, "3 hours": 3*60*60, "6 hours": 6*60*60,
            "12 hours": 12*60*60, "1 day": 24*60*60, "2 days": 2*24*60*60,
            "3 days": 3*24*60*60, "5 days": 5*24*60*60, "1 week": 7*24*60*60,
            "2 weeks": 2*7*24*60*60, "1 month": 4*7*24*60*60,
        }
        menu = MessageActionRowBuilder().add_select_menu("snooze_menu")
        for name, value in snooze_times.items():
            menu.add_option(f"snooze for {name}", str(value)).add_to_menu()
        menu = menu.add_to_container()

        embed = Embed(description='')
        if self.remind_text:
            embed.description += f"{self.remind_text} \n"
        dummy_message = mock.Mock(id=self.message_id, channel_id=self.channel_id)
        link = hikari.Message.make_link(dummy_message, self.guild_id)
        if self.message_id != 0:
            d = f"[jump to your message]({link}) \n"
            embed.description += d
        user = await self.bot.rest.fetch_user(self.creator_id)
        embed.title = f"Reminder"
        embed.description += user.mention
        embed.set_thumbnail(user.avatar_url)
        msg = await self.bot.rest.create_message(channel=self.channel_id, embed=embed, user_mentions=True, components=[menu])
        value, event, _ = await self.bot.wait_for_interaction(
            custom_id="snooze_menu",
            user_id=self.creator_id,
            message_id=msg.id,
        )
        if (
            not isinstance(event, hikari.InteractionCreateEvent) 
            or not isinstance(event.interaction, hikari.ComponentInteraction)
        ):
            await msg.edit(embed=embed, components=[])
            return
        # inform user
        embed.description += f"\nremind you in: <t:{int(time.time())+int(value)}:R> again"
        event.interaction.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)
        await msg.edit(embed=embed, components=[])
        # prepare and start new reminder
        reminder = HikariReminder(self.channel_id, self.creator_id, self.message_id, offset_hours=self.hour_offset)
        reminder.wait_until = int(time.time() + int(value))
        reminder.datetime = datetime.datetime.fromtimestamp(reminder.wait_until)
        reminder.remind_text = self.remind_text
        reminder.in_seconds = int(value)
        if reminder.in_seconds >= Reminders.REMINDER_UPDATE:
            loop = asyncio.get_event_loop()
            asyncio.Task(reminder.store_reminder(), loop=loop)
        else:
            asyncio.Task(reminder.schedule())
        
        
    async def destroy_reminder(self):
        """
        Deleting the DB entry, and the element in the set
        """
        if not self.id:
            return  # reminder was to short to being stored
        record = await Reminders.delete_reminder_by_id(self.id)
        Reminders.delete_from_set(record)

    def from_database(
        self,
        id: int,
        timestamp: datetime.datetime,
        remind_text: Optional[str] = None,
    ):
        self.id = id
        self.datetime = timestamp
        self.remind_text = remind_text
        self.wait_until = self.datetime.timestamp()
        asyncio.Task(
            self.schedule(),
            loop=asyncio.get_running_loop(),
        )
        

    @staticmethod
    def parse(query: str) -> Tuple[datetime.datetime, str]:
        """
        RETURNS:
        --------
            - (datetime.datetime) the datetime where the reminder should trigger 
            - (str) the message
        """
        gen = PeekIterator(query, " ")
        query.replace(" ", "")
        num_str = ""
        unit: Optional[TimeUnits] = None
        for i, word in enumerate(gen):
            print(f"{i}: {word=}")
        


    @classmethod
    def unit_to_seconds(cls, unit: str, unit_amount: Union[int, float]) -> float:
        in_seconds: float = 0

        unit = unit.lower()
        matches = []
        for a in TimeUnits.aliases:
            if unit == a:
                matches.append(a)
                break
            # check if unit is given in plural
            if len(unit)-1 == len(a) and unit.endswith("s") and len(unit) > 1:
                in_seconds += cls.unit_to_seconds(unit[:-1], unit_amount)
        if not matches:
            raise RuntimeError(f"`{unit}` is an unknown time unit")
        if len(matches) > 1:
            raise RuntimeError(f"Found multiple time units ({matches}) with the given unit `{unit}`")

class Reminders:
    db: Database
    bot: lightbulb.BotApp
    running_reminders = set()
    REMINDER_UPDATE = REMINDER_UPDATE
    
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @classmethod
    async def init_bot(cls, bot: lightbulb.BotApp):
        cls.bot = bot
        cls.db = bot.db
        await cls.clean_up_reminders()

    @classmethod
    async def clean_up_reminders(cls):
        """
        Deletes reminders which are in the past.
        """
        sql = """
        DELETE FROM reminders
        WHERE remind_time < $1
        RETURNING *
        """
        records = await cls.db.fetch(sql, datetime.datetime.now())
        log.info(f"Ceaned up reminders; {len(records)} reminders where removed")

    @classmethod
    def add_reminders_to_set(cls, records: List[asyncpg.Record]):
        """
        Add a reminder to the set of running reminders.
        Used as cache to avoid duplicates.

        Args:
        -----
        records: List[asyncpg.Record]
            The records which contain the reminder data which should be added to the set.
        """
        for r in records:
            if r["reminder_id"] in cls.running_reminders:
                continue
            cls.running_reminders.add(r["reminder_id"])
            log.debug(f"add reminder | id: {r['reminder_id']}; text: {'remind_text'}")
            reminder = HikariReminder(
                channel_id=r["channel_id"],
                creator_id=r["creator_id"],
                message_id=r["message_id"],
            )
            reminder.from_database(
                r["reminder_id"],
                r["remind_time"],
                r["remind_text"],
            )

    @classmethod
    def delete_from_set(cls, reminder: asyncpg.Record):
        """
        remove a reminder form the cache set.
        """
        log.debug(f"del: {reminder}")
        try:
            cls.running_reminders.remove(reminder["reminder_id"])
        except Exception:
            log.warning(f"utils.Reminders - delte_from_set \n {traceback.format_exc()}")

    @classmethod
    async def add_reminder(cls, reminder: HikariReminder) -> int:
        """
        Adds a reminder to the DB

        Args:
        -----
            - reminder: (`~.Reminder`) the reminder instance to take properties from

        Returns:
        --------
            - (int) the reminder_id
        """
        sql = """
        INSERT INTO reminders(remind_text, channel_id, creator_id, message_id, remind_time)
        VALUES($1, $2, $3, $4, $5)
        RETURNING reminder_id
        """
        id = await cls.db.row(
            sql,
            reminder.remind_text, 
            reminder.channel_id, 
            reminder.creator_id,
            reminder.message_id,
            reminder.datetime
        )
        return id

    @classmethod
    async def fetch_reminder_by_id(cls, id: int) -> Optional[asyncpg.Record]:
        """
        Fetches the reminder by id from the DB

        Args:
        -----
            - id (int) the id of the existing reminder

        Returns:
        --------
            - (`~.HikariReminder`, None) the reminder object to the given id - or None when nothing was found
        """
        sql = """
        SELECT * FROM reminders
        WHERE reminder_id = $1
        """
        record = await cls.db.row(sql, id)
        if not record:
            return None
        return record

    @classmethod
    async def delete_reminder_by_id(cls, id: int) -> asyncpg.Record:
        """
        Fetches the reminder by id from the DB

        Args:
        -----
            - id (int) the id of the existing reminder

        Returns:
        --------
            - (int, None) the id of the deleted reminder
        """
        sql = """
        DELETE FROM reminders
        WHERE reminder_id = $1
        RETURNING *
        """
        record = await cls.db.row(sql, id)
        if not record:
            return None
        return record

    @classmethod
    def set_db(cls, db: Database):
        cls.db = Database
