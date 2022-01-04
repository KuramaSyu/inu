from typing import *
import json
import logging
import datetime
import asyncio
from enum import Enum
import time

import hikari
from hikari.embeds import Embed
import lightbulb
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
        """
        parses the query to wait time in seconds and unused query (the remind text).
        """
        gen = NumberWordIterator(self.query)
        str_unit = ""
        amount: float = None
        matches = {}
        # iterate through query. each iteration is a float or a str.
        # if its a float, it will be stored as amount
        # if its a str, its will be stored as the unit
        # -> converting str to a unit
        # actual add (unit to seconds) * amount (by default 1) to total waiting seconds 
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

                str_unit = ""
                amount = None
        #for str_unit, amount in matches.items():



class BaseReminder:
    def __init__(self, query: str):
        self._query = query
        if self._query:
            self.time_parser = TimeParser(self._query)
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
    ):
        super().__init__(query=query)
        self.message_id = message_id
        self.channel_id = channel_id
        self.creator_id = creator_id
        self.ctx = ctx

        if self._query:
            if self.in_seconds > 4*60:
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
        log.debug(Reminders.db)
        self.id = await Reminders.add_reminder(self)

    async def schedule(self):
        await asyncio.sleep(self.remaining_time)
        await self.destroy_reminder()
        await self.send_message()

    async def send_message(self):
        embed = Embed(title="Reminder", description='')
        if self.message_id != 0:
            if self.ctx:
                d = f"[jump to your message]({self.ctx.event.message.make_link(self.ctx.guild_id)}) \n"
            else:
                d = f"[jump to your message]({(await Reminders.bot.rest.fetch_message(self.channel_id, self.message_id)).make_link(self.guild_id)}) \n"
            embed.description += d
        if self.remind_text:
            embed.description += self.remind_text
        if self.ctx:
            asyncio.Task(self.ctx.author.send(embed=embed))
        else:
            async def send(self):
                await (await Reminders.bot.rest.fetch_user(self.creator_id)).send(embed=embed)
            asyncio.Task(send(self))
        if self.guild_id:
            asyncio.Task(self.ctx.bot.rest.create_message(self.channel_id, embed=embed))
        
    async def destroy_reminder(self):
        """
        Deleting the DB entry
        """
        if not self.id:
            return  # reminder was to short to being stored
        await Reminders.delete_reminder_by_id(self.id)

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
    
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @classmethod
    async def init_bot(cls, bot: lightbulb.BotApp):
        cls.bot = bot
        cls.db = bot.db
        log.info("start cleaning task")
        print("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        await cls.clean_up_reminders()

    @classmethod
    async def clean_up_reminders(cls):
        sql = """
        DELETE FROM reminders
        WHERE remind_time < $1
        RETURNING *
        """
        records = await cls.db.fetch(sql, datetime.datetime.now())
        log.info(f"Ceaned up reminders; {len(records)} reminders where removed")

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
        log.debug(cls.db)
        id = await cls.db.row(
            sql,
            reminder.remind_text, 
            reminder.channel_id, 
            reminder.creator_id,
            reminder.message_id,
            reminder.datetime
        )
        log.debug(id)
        return id

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
        reminder = HikariReminder(
            message_id=record["message_id"],
            channel_id=record["channel_id"],
            creator_id=record["creator_id"],
        )
        reminder.from_database(record["id"], record["remind_time"], record["remind_text"])

    @classmethod
    async def delete_reminder_by_id(cls, id: int) -> Optional[int]:
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
        return record["reminder_id"]

    @classmethod
    def set_db(cls, db: Database):
        cls.db = Database
