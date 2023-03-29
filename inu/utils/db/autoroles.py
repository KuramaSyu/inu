from typing import *

from datetime import datetime, timedelta
from abc import ABC, abstractmethod, abstractproperty
import asyncio

import hikari
from hikari.impl import MessageActionRowBuilder
from hikari import Member

from core import Table, Inu

autorole_table = Table("autoroles")
AnyAutoroleEvent = TypeVar('AnyAutoroleEvent', bound="AutoroleEvent", covariant=True)


class AutoroleEvent(ABC):
    
    def __init__(
        self,
        bot: Inu,
        guild_id: int,
        duration: timedelta,
        role_id: int,
        id: int | None = None
    ):
        self.id = id
        self.guild_id = guild_id
        self.duration = duration
        self.role_id = role_id
        self.bot = bot


    @property
    @abstractmethod
    def event_id(self) -> int:
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def initial_call(self):
        ...


    @abstractmethod
    async def callback(self, event: hikari.Event):
        ...
    

    @abstractmethod
    async def add_to_db(self):
        ...

    
    @abstractmethod
    async def remove_from_db(self):
        ...

class AutoroleAllEvent(AutoroleEvent):
    name = "Default Role"
    event_id = 0

    async def initial_call(self) -> None:
        """asigns the role to all members currently in the guild"""
        guild_members: Sequence[Member] = await self.bot.rest.fetch_members(self.guild_id)
        tasks = []
        # asign `self.role_id` to all members in `guild_members`
        for member in guild_members:
            tasks.append(
                asyncio.create_task(member.add_role(self.role_id))
            )
        await asyncio.gather(*tasks)


    async def callback(self, event: hikari.MemberCreateEvent) -> None:  # type: ignore[override]
        """asigns the role to the member when they join a guild"""
        await event.member.add_role(self.role_id)

    async def add_to_db(self):
        """adds the autorole to the database"""
        await autorole_table.insert(
            values={
                "guild_id": self.guild_id,
                "duration": self.duration,
                "role_id": self.role_id,
                "event_id": self.event_id
            }
        )
        

    async def remove_from_db(self):
        """removes the autorole from the database"""
        if self.id is None:
            raise ValueError("id is None")
        await autorole_table.delete_by_id("id", self.id)


class AutoroleBuilder:
    guild: int | hikari.Guild | None = None
    duration: timedelta | None = None
    role: int | hikari.Role | None = None
    event: Type[AutoroleEvent] | None = None
    id: int | None = None

    def build(self) -> AutoroleEvent:
        if None in [self.guild_id, self.duration, self.role_id, self.event]:
            raise ValueError("None in [self.guild_id, self.duration, self.role_id, self.event]")
        return self.event(
            guild_id=self.guild_id, 
            duration=self.duration, 
            role_id=self.role_id, 
            bot=AutoroleManager.bot
        )  # type: ignore
    
    @property
    def guild_id(self) -> int:
        if isinstance(self.guild, hikari.Guild):
            return self.guild.id
        elif isinstance(self.guild, int):
            return self.guild
        else:
            raise ValueError("self.guild is not a hikari.Guild or int")
        
    @property
    def role_id(self) -> int:
        if isinstance(self.role, hikari.Role):
            return self.role.id
        elif isinstance(self.role, int):
            return self.role
        else:
            raise ValueError("self.role is not a hikari.Role or int")

    
    

    



class AutoroleManager():
    table = Table("autoroles")
    id_event_map: Dict[int, Type[AutoroleEvent]] = {
        0: AutoroleAllEvent
    }
    bot: Inu
    
    @classmethod
    def set_bot(cls, bot: Inu) -> None:
        cls.bot = bot

    @classmethod
    async def fetch_events(
        cls,
        guild_id: int,
        event: Type[AutoroleEvent],
    ):
        """fetches all autoroles with the given `guild_id` and `event_id`
        
        Args:
        -----
        `guild_id : int`
            the guild id of the autoroles to fetch
        `event : Type[AutoroleEvent]`
            the event type of the autoroles to fetch
        
        Returns:
        --------
        `List[AutoroleEvent]`
            a list of all autoroles with the given `guild_id` and `event_id`
        """
        event_id = event.event_id
        records = await cls.table.select(where={"guild_id": guild_id, "event_id": event_id})
        events: List[AutoroleEvent] = []
        for record in records:
            event = cls._build_event(record)
            events.append(event)


    @classmethod
    async def _build_event(cls, record: dict) -> AutoroleEvent:
        event_id = record["event_id"]
        event = cls.id_event_map[event_id]
        event = event(
            guild_id=record["guild_id"],
            duration=record["duration"],
            role_id=record["role_id"],
            bot=cls.bot,
            id=record["id"]
        )
        return event
    
    @classmethod
    async def add_event(cls, event: AutoroleEvent) -> None:
        await event.add_to_db()
