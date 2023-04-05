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
        duration: timedelta | None,
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
        """The id of the event"""
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of this event"""
        ...

    @abstractmethod
    async def initial_call(self):
        """
        initial call which needs to be done once at the start
        before any callback
        """
        ...


    @abstractmethod
    async def callback(self, event: hikari.Event):
        """
        callback for what the event actually does

        Parameters
        ----------
        event : hikari.Event
            the event that triggered the callback
        """
        ...
    

    @abstractmethod
    async def add_to_db(self):
        """adds the entry to the database"""
        ...

    
    @abstractmethod
    async def remove_from_db(self):
        """removes the entry from the database"""
        ...

    @abstractmethod
    async def sync_to_db(self):
        """updates the entry in the database"""
        ...



class AutoroleAllEvent(AutoroleEvent):
    name = "Default Role"
    event_id = 0
    db_event_id = None

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
        if self.db_event_id is None:
            await autorole_table.insert(
                [],
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

    async def sync_to_db(self):
        """syncs the autorole to the database"""
        if self.id is None:
            raise ValueError("id is None")
        await autorole_table.update(
            set={
                "guild_id": self.guild_id,
                "duration": self.duration,
                "role_id": self.role_id,
                "event_id": self.event_id
            },
            where={"id": self.id},
        )

class AutoroleBuilder:
    _guild: int | hikari.Guild | None = None
    _duration: timedelta | None = None
    _role: int | hikari.Role | None = None
    _event: Type[AutoroleEvent] | None = None
    _changed: bool = False
    id: int | None = None

    
    @property
    def is_saveable(self) -> bool:
        """weather or not the builder is saveable as an `AutoroleEvent`"""
        return not None in (self._guild, self._duration, self._role, self._event)
    
    def build(self) -> AutoroleEvent:
        if None in [self.guild_id, self.role_id, self.event]:
            raise ValueError("None in [self.guild_id, self.role_id, self.event]")
        event = self.event(
            guild_id=self.guild_id, 
            duration=self.duration, 
            role_id=self.role_id, 
            bot=AutoroleManager.bot
        )  # type: ignore
        if self.id:
            event.id = self.id
        return event


    def _mark_as_changed(self) -> None:
        """marks the builder as changed, if it has an id"""
        if self.id:
            self._changed = True


    @property
    def guild(self) -> int | hikari.Guild | None:
        return self._guild
    
    @guild.setter
    def guild(self, value: int | hikari.Guild | None) -> None:
        self._mark_as_changed()
        self._guild = value

    @property
    def duration(self) -> timedelta | None:
        return self._duration
    
    @duration.setter
    def duration(self, value: timedelta | None) -> None:
        self._mark_as_changed()
        self._duration = value

    @property
    def role(self) -> int | hikari.Role | None:
        return self._role
    
    @role.setter
    def role(self, value: int | hikari.Role | None) -> None:
        self._mark_as_changed()
        self._role = value

    @property
    def event(self) -> Type[AutoroleEvent] | None:
        return self._event
    
    @event.setter
    def event(self, value: Type[AutoroleEvent] | None) -> None:
        self._mark_as_changed()
        self._event = value

    async def save(self) -> bool:
        """
        returns wether or not the event was saved
        """
        if self.id:
            # update
            if not self._changed:
                return False
        
            event: AutoroleEvent = self.build()
            await event.sync_to_db()
            self._changed = False
            return True
        else:
            # insert
            if not self.is_saveable:
                return False
            event: AutoroleEvent = self.build()
            await event.add_to_db()
            return True
        
    async def delete(self) -> bool:
        """
        returns wether or not the event was deleted
        """
        if self.id:
            event: AutoroleEvent = self.build()
            await event.remove_from_db()
            return True
        return False
        
    def from_db(self, record: dict) -> "AutoroleBuilder":
        """syncs this builder with a database record
        
        Parameters
        ----------
        record : dict
            the database record
            
        
        Returns
        -------
        AutoroleBuilder :
            self
        """
        self.guild = record["guild_id"]
        self.duration = record["duration"]
        self.role = record["role_id"]
        self.event = AutoroleManager.id_event_map[record["event_id"]]
        self.id = record["id"]
        return self

    def from_event(self, event: AutoroleEvent) -> "AutoroleBuilder":
        """syncs this builder with an AutoroleEvent
        
        Parameters
        ----------
        event : AutoroleEvent
            the AutoroleEvent
        
        Returns
        -------
        AutoroleBuilder :
            self
        """
        self.guild = event.guild_id
        self.duration = event.duration
        self.role = event.role_id
        self.event = event.__class__
        self.id = event.id
        return self
    
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
        event: Type[AutoroleEvent] | None = None,
    ):
        """fetches all autoroles with the given `guild_id` and `event_id`
        
        Args:
        -----
        `guild_id : int`
            the guild id of the autoroles to fetch
        `event : Type[AutoroleEvent] | None`
            the event type of the autoroles to fetch
        
        Returns:
        --------
        `List[AutoroleEvent]`
            a list of all autoroles with the given `guild_id` and `event_id`
        """
        if event is not None:
            event_id = event.event_id
        else:
            event_id = None
        where = {"guild_id": guild_id}
        if event_id is not None:
            where["event_id"] = event_id
        records = await cls.table.select(where=where)
        events: List[AutoroleEvent] = []
        for record in records:
            e = cls._build_event(record)
            events.append(e)
        return events

    @classmethod
    async def wrap_events_in_builder(cls, events: List[AutoroleEvent]) -> List[AutoroleBuilder]:
        """wraps a list of AutoroleEvents in AutoroleBuilders
        
        Args:
        -----
        `events : List[AutoroleEvent]`
            the list of AutoroleEvents to wrap
        
        Returns:
        --------
        `List[AutoroleBuilder]`
            a list of AutoroleBuilders with the same data as the given events
        """
        builders: List[AutoroleBuilder] = []
        roles = cls.bot.cache.get_roles_view_for_guild(events[0].guild_id)
        for event in events:
            builder = AutoroleBuilder().from_event(event)
            builder.role = roles.get(event.role_id)
            # reset the changed flag triggered by role proterty setter
            builder._changed = False
            builders.append(builder)
        
        return builders
    

    @classmethod
    def _build_event(cls, record: dict) -> AutoroleEvent:
        """builds an AutoroleEvent from a database record
        
        Args:
        -----
        `record : dict`
            the database record
        
        Returns:
        --------
        `AutoroleEvent`
            an AutoroleEvent with the same data as the given record
        """
        event_id = record["event_id"]
        event_type = cls.id_event_map[event_id]
        event = event_type(
            guild_id=record["guild_id"],
            duration=record["duration"],
            role_id=record["role_id"],
            bot=cls.bot,
            id=record["id"]
        )
        return event
    
    @classmethod
    async def add_event(cls, event: AutoroleEvent) -> None:
        """adds an AutoroleEvent to the database
        this just calls the event method `add_to_db`
        
        Args:
        -----
        `event : AutoroleEvent`
            the AutoroleEvent to add
        
        Returns:
        --------
        `None`
        """
        await event.add_to_db()
