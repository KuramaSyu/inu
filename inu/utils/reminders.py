from typing import *
import json
import logging
import datetime
import asyncio
from enum import Enum
import time

from lightbulb.context import Context

from .db import Database
from .string_crumbler import PeekIterator, NumberWordIterator

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class TimeUnits(Enum):
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
        "aliases": ["month", "mon", "m", "months"],
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


class TimeConverter:
    @classmethod
    def is_parable(cls, query: str) -> bool:
        pass

    @classmethod
    def to_seconds(cls, unit: dict, amount: Union[int, float]) -> float:
        return float(unit.value["in_seconds"] * amount)

    @classmethod
    def all_aliases(cls) -> List[str]:
        return [alias for unit in [unit.value for unit in TimeUnits] for alias in unit["aliases"]]

    @staticmethod
    def get_unit(str_unit: str) -> Optional[TimeUnits]:
        for unit in TimeUnits.__members__.values():
            if str_unit in unit.value["aliases"]:
                return unit

class TimeParser:
    def __init__(self, query: str):
        self.query = query
        self.in_seconds: float = 0
        self.matches: Dict[TimeUnits, float] = {}
        self.now: datetime.datetime = datetime.datetime.now()
        self.unresolved = []
        self.unused_query = ""
        self.parse()


    def parse(self):
        gen = NumberWordIterator(self.query)
        str_unit = ""
        amount: float = None
        matches = {}
        for item in gen:
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
                    if self.unused_query == "":
                        self.unused_query = self.query[gen.last_word_index-1:]
                    break
                self.in_seconds += TimeConverter.to_seconds(unit, amount)
                if self.matches.get(unit.name):
                    self.matches[unit.name] += amount
                else:
                    self.matches[unit.name] = amount

                unit = ""
                amount = None
        #for str_unit, amount in matches.items():



class BaseReminder:
    def __init__(self, query: str):
        self.query = query
        self.time_parser = TimeParser(query)
        self.remind_text = self.time_parser.unused_query
        self.in_seconds = self.time_parser.in_seconds
        self.wait_until: float = time.time() + self.in_seconds
        self.datetime = datetime.datetime.fromtimestamp(self.wait_until)
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
        message_id: int,
        channel_id: int,
        creator_id: int,
        query: Optional[str] = None, 
        id: Optional[int] = None,
    ):
        super.__init__(query=query)
        self.db = Reminders.db

        self.message_id = message_id
        self.channel_id = channel_id
        self.creator_id = creator_id

        if self.in_seconds > 10*60:
            loop = asyncio.get_event_loop()
            task = loop.create_task(self.store_reminder())

    async def store_reminder(self):
        pass

    async def schedule(self):
        await asyncio.sleep(self.remaining_time)
        await self.destroy_reminder()

    async def destroy_reminder(self):
        """
        Deleting the DB entry
        """
        pass
      
        
        
        

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
    
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @classmethod
    def set_db(cls, database: Database):
        cls.db = database

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
        INSERT INTO TABLE reminders(remind_time, remind_text, channel_id, creator_id, message_id)
        VALUES($1, $2, $3, $4, $5)
        RETURNING reminder_id
        """
        return await cls.db.execute(
            sql, 
            reminder.datetime, 
            reminder.remind_text, 
            reminder.channel_id, 
            reminder.creator_id,
            reminder.message_id
        )

    @classmethod
    async def fetch_reminder_by_id(cls, id: int) -> Optional[HikariReminder]:
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
        reminder = hikari_reminder
