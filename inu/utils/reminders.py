from typing import *
import json
import typing as t
import logging
import datetime
import asyncio
from lightbulb.context import Context

from .db import Database
from .string_crumbler import PeekIterator

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class Reminder:
    def __init__(self, query: str, ctx: Context):
        self.query = query
        self.db = Reminders.db
        self.id = None
        self.datetime = None
        self.remind_text = None

    def process_query(self) -> Tuple(datetime.datetime, str):
        """
        RETURNS:
        --------
            - (datetime.datetime) the datetime where the reminder should trigger 
            - (str) the message
        """
        gen = PeekIterator(self.query, " ")

class Reminders:
    db: Database
    
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @classmethod
    def set_db(cls, database: Database):
        cls.db = database

    @classmethod
    async def add_reminder(cls, query: str):
        pass
