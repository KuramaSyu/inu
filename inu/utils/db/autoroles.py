from typing import *

from datetime import datetime, timedelta
from abc import ABC, abstractmethod, abstractproperty
import asyncio

import hikari
from hikari.impl import MessageActionRowBuilder
from hikari import Member

from core import Table, Inu, getLogger

log = getLogger(__name__)

autorole_table = Table("autoroles.events")
autorole_user_table = Table("autoroles.instances")
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

    @abstractmethod
    async def on_delete(self, record:Dict[str,Any]):
        """Gets called, when an entrie from the database gets deleted"""
        ...




class AutoroleAllEvent(AutoroleEvent):
    name = "Default Role"
    event_id = 0
    id = None

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
        if self.id is None:
            return await autorole_table.insert(
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

    async def on_delete(self, record:Dict[str,Any]):
        ...



class VoiceActivityEvent(AutoroleEvent):
    name = "Voice Activity"
    event_id = 1
    id = None
    user_id = None

    async def initial_call(self) -> None:
        pass

    async def callback(self, event: hikari.VoiceServerUpdateEvent) -> None:
            """
            Callback method for handling voice server update events.

            Args:
                event (hikari.VoiceServerUpdateEvent): The voice server update event.

            Returns:
                None
            """
            pass
    
    async def renew_user_duration(self, user_id: int, guild_id: int, event_id: int = 1) -> None:
            """
            Renews the duration of a user's role in the autoroles system.

            Args:
                user_id (int): The ID of the user.
                guild_id (int): The ID of the guild.
                event_id (int, optional): The ID of the event. Defaults to 1.

            Returns:
                None
            """
            record = await autorole_user_table.fetch(
                """
                INSERT INTO autoroles.instances (user_id, guild_role, expires_at)
                SELECT $1, gr.id, NOW() + gr.duration
                FROM autoroles.events AS gr
                WHERE gr.event_id = $2 AND gr.guild_id = $3
                ON CONFLICT (user_id, guild_role) DO UPDATE
                SET expires_at = EXCLUDED.expires_at;
                """, user_id, event_id, guild_id
            )
            member: hikari.Member = self.bot.cache.get_member(guild_id, user_id)
            if not self.role_id in member.role_ids:
                await member.add_role(self.role_id)

    async def delete_user_roles(self, user_id: int, guild_id: int, event_id: int = 1) -> None:
            """
            Deletes the user role for a specific user in a guild.

            Args:
                user_id (int): The ID of the user.
                guild_id (int): The ID of the guild.
                event_id (int, optional): The ID of the event. Defaults to 1.
            """
            records = await autorole_user_table.delete(
                where={
                    "user_id": user_id,
                    "guild_id": guild_id,
                    "event_id": event_id
                }
            )
            user_ids = set([record["user_id"] for record in records])
            for user_id in user_ids:
                member = await self.bot.rest.fetch_member(guild_id, user_id)
                await member.remove_role(self.role_id)

    async def delete_user_role_by_id(self, record: Dict[str, Any]) -> None:
            """
            Deletes the user role for a specific user in a guild.

            Args:
                record (Dict[str, Any]): The record containing information about the user role.

            Returns:
                None
            """
            await autorole_user_table.delete_by_id("id", record["id"])
            member = await self.bot.rest.fetch_member(record["guild_id"], record["user_id"])
            await member.remove_role(self.role_id)

    async def add_to_db(self):
        """adds the autorole to the database"""
        if self.id is None:
            value = await autorole_table.insert(
                [],
                values={
                    "guild_id": self.guild_id,
                    "duration": self.duration,
                    "role_id": self.role_id,
                    "event_id": self.event_id
                }
            )
            VoiceAutoroleCache.add(self.guild_id)
            return value

    async def remove_from_db(self):
        """removes the autorole from the database"""
        if self.id is None:
            raise ValueError("id is None")
        await autorole_table.delete_by_id("id", self.id)
        VoiceAutoroleCache.remove(self.guild_id)

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

    async def on_delete(self, record:Dict[str, Any]):
        """removes the role from the user"""
        log.info(f"deleting {record=}")
        await self.delete_user_role_by_id(record)



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
            Saves the AutoroleEvent object to the database.

            Returns:
                bool: True if the event was saved successfully, False otherwise.

            If the event already has an id, it updates the existing record in the database.
            If the event has no id, it inserts a new record into the database and calls the `initial_call` method.
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
                await event.initial_call()
                value = await event.add_to_db()
                self.id = value[0]["id"]
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
    table = Table("autoroles.events")
    id_event_map: Dict[int, Type[AutoroleEvent]] = {
        0: AutoroleAllEvent,
        1: VoiceActivityEvent
    }
    bot: Inu
    deletion_scheduled: set[int] = set()
    
    @classmethod
    def set_bot(cls, bot: Inu) -> None:
        cls.bot = bot

    @classmethod
    async def fetch_instances(
        cls,
        guild_id: int | None = None,
        event: Type[AutoroleEvent] | None = None,
    ) -> List[Dict[Literal["id", "user_id", "expires_at", "event_id", "role_id"], Any]]:
        """
        Fetches all instances of autoroles for a specific guild from the database.

        Args:
            guild_id (int, optional): The ID of the guild. Defaults to None.
            event (Type[AutoroleEvent], optional): The event type. Defaults to None.

        Returns:
            List[Dict[Literal["id", "user_id", "expires_at", "event_id", "role_id"], Any]]
        """
        records = await autorole_user_table.fetch(
        f"""
        SELECT events.id, inst.user_id, inst.expires_at, events.event_id, events.role_id
        FROM {autorole_user_table.name} inst
        INNER JOIN {autorole_table.name} events ON events.id = inst.guild_role
        WHERE events.guild_id = $1 AND events.event_id = $2

        """, guild_id, event.event_id
        )
        return records
    
    @classmethod
    async def fetch_events(
        cls,
        guild_id: int | None = None,
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
        where = {}
        if guild_id is not None:
            where["guild_id"] = guild_id
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

    @classmethod
    async def remove_expired_autoroles(cls, expires_in: int) -> None:
            """
            Removes expired autoroles from the autorole_user_table.

            Args:
                expires_in (int): The number of seconds to delete autoroles. now + this.

            Returns:
                None
            """
            records = await autorole_user_table.fetch(
                """
                SELECT ur.id AS id, ur.user_id, ur.expires_at, gr.guild_id, gr.role_id, gr.event_id, gr.duration FROM autoroles.instances ur
                INNER JOIN autoroles.events gr ON gr.id = guild_role
                WHERE expires_at < $1
                """, datetime.now() + timedelta(seconds=expires_in)
            )
            for record in records:
                await cls._schedule_deletion(record, (record["expires_at"] - datetime.now()).total_seconds())

    @classmethod
    async def _schedule_deletion(cls, record: Dict[str, Any], delay: int) -> None:
        """
        Schedules the deletion of an autorole.

        Args:
            event (AutoroleEvent): The autorole event.
            delay (int): The delay in seconds.

        Returns:
            None
        """
        event = cls._build_event(record)
        if event.id in cls.deletion_scheduled:
            return
        log.debug(f"scheduling deletion of {event.id} in {delay} seconds")
        cls.deletion_scheduled.add(event.id)
        await asyncio.sleep(delay)
        await event.on_delete(record)
        cls.deletion_scheduled.remove(event.id)

    @classmethod
    async def delete_guild(cls, guild_id: int) -> None:
        """deletes all autoroles for a guild
        
        Args:
        -----
        `guild_id : int`
            the guild id to delete autoroles for
        
        Returns:
        --------
        `None`
        """
        await autorole_table.delete(where={"guild_id": guild_id})



class MetaVoiceAutoroleCache(type):
    _guilds: Set[int] = set()
    def __contains__(cls, guild_id: int) -> bool:
        return guild_id in cls._guilds
    


class VoiceAutoroleCache(metaclass=MetaVoiceAutoroleCache):
    _guilds: Set[int] = set()

    @classmethod
    def add(cls, guild_id: int) -> None:
        cls._guilds.add(guild_id)

    @classmethod
    def extend(cls, guild_ids: Iterable[int]) -> None:
        cls._guilds.update(guild_ids)

    @classmethod
    def remove(cls, guild_id: int) -> None:
        try:
            cls._guilds.remove(guild_id)
        except KeyError:
            pass

    @classmethod
    async def sync(cls) -> None:
        events = await AutoroleManager.fetch_events(None, VoiceActivityEvent)
        guilds = [event.guild_id for event in events]
        log.info(f"synced {len(guilds)} voice autoroles for cache")
        cls._guilds.update(guilds)