import asyncio
import abc
from typing import *
from datetime import datetime, timedelta
from xml.etree.ElementPath import prepare_parent

import hikari
from hikari import COMMAND_RESPONSE_TYPES, Embed, ComponentInteraction, CommandInteraction, InteractionCreateEvent, Message, ResponseType, Snowflake
from hikari.impl import MessageActionRowBuilder
from datetime import timedelta

from . import Response

if TYPE_CHECKING:
    from .base import InuContextBase



class InteractionResponse(Response):
    def __init__(self, interaction: ComponentInteraction) -> None:
        self.interaction: ComponentInteraction = interaction
        self._deferred: bool = False
        self._responded: bool = False
        self._response_lock: asyncio.Lock = asyncio.Lock()
    
    async def defer(self, ephemeral: bool = False, update: bool = False):
        await self._response_lock.acquire()
        
        if self._responded or self._deferred:
            return
        
        flags = hikari.MessageFlag.NONE
        if ephemeral:
            flags = hikari.MessageFlag.EPHEMERAL
            
        match update:
            case True:
                response_type = hikari.ResponseType.DEFERRED_MESSAGE_UPDATE
            case False:
                response_type = hikari.ResponseType.DEFERRED_MESSAGE_CREATE
                
        await self.interaction.create_initial_response(response_type, flags=flags)
        self._response_lock.release()
        
    async def respond(
        self,
        embeds: list[Embed] | None = None,
        content: str | None = None,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: list[MessageActionRowBuilder] | None = None,
    ):
        pass
    
    
async def delete_after_task(time: timedelta, interaction: ComponentInteraction | CommandInteraction):
    await asyncio.sleep(time.total_seconds())
    await interaction.delete_initial_response()



class BaseResponseState(abc.ABC):
    interaction: CommandInteraction | ComponentInteraction
    responses: List[Message]
    context: 'InuContextBase'
    last_response: datetime

    def __init__(
        self, 
        interaction: ComponentInteraction | CommandInteraction, 
        context: 'InuContextBase'
    ) -> None:
        self._deferred: bool = False
        self._responded: bool = False
        self._response_lock: asyncio.Lock = asyncio.Lock()
        self.last_response: datetime = self.created_at
        
    def change_state(self, new_state: Type["BaseResponseState"]):
            """
            Changes the ResponseState of the parent `InuContextBase` to the new state, coping `interaction` and `context`
            """
            state = new_state(
                self.interaction,
                self.context
            )
            self.context.set_response_state(state)
            
    @abc.abstractmethod
    async def respond(
        self,
        embeds: List[hikari.Embed] | None = None,
        content: str | None = None,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> None:
        ...
        
    async def edit_last_response(
        self,
        embeds: List[hikari.Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> None:
        await self.interaction.edit_message(
            self.responses[-1],
            embeds=embeds,
            content=content,
            components=components
        )

    @abc.abstractmethod
    async def edit(
        self,
        embeds: List[hikari.Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
        message_id: Snowflake | None = None,
    ):
        """Edits per default the first response or makes the initial response if it hasn't been made yet.

        Args:
            embeds (List[hikari.Embed] | None, optional): _description_. Defaults to None.
            content (str | None, optional): _description_. Defaults to None.
            components (List[MessageActionRowBuilder] | None, optional): _description_. Defaults to None.
            message_id (Snowflake | None, optional): _description_. Defaults to None.
        """
        ...
        
    @abc.abstractmethod
    async def defer(self, update: bool = False) -> None:
        ...
        
    @property
    def created_at(self) -> datetime:
        return self.interaction.created_at
    
    @property
    @abc.abstractmethod
    def is_valid(self) -> bool:
        ...
        
        
class InitialResponseState(BaseResponseState):

        
    
    @property
    def is_valid(self) -> bool:
        return (datetime.now() - self.last_response) < timedelta(seconds=3)
        
    async def respond(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: List[MessageActionRowBuilder] | None = None,
    ):
        await self._response_lock.acquire()
        
        if self._responded or self._deferred:
            return
        
        flags = hikari.MessageFlag.NONE
        if ephemeral:
            flags = hikari.MessageFlag.EPHEMERAL
            
        await self.interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            embeds=embeds,
            content=content,
            components=components,
            flags=flags
        )
        self.last_response = datetime.now()
        self.change_state(CreatedResponseState)
        self._response_lock.release()
        
    async def edit(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
        message_id: Snowflake | None = None,
    ) -> None:
        await self._response_lock.acquire()
        await self.interaction.create_initial_response(
            ResponseType.MESSAGE_UPDATE, content,  # type: ignore
            embeds=embeds,
            components=components,
        )
        self.last_response = datetime.now()
        self.change_state(CreatedResponseState)
        self._response_lock.release()
        
    async def defer(self, update: bool = False) -> None:
        await self._response_lock.acquire()
        
        if self._responded or self._deferred:
            return
        
        if update:
            response_type = hikari.ResponseType.DEFERRED_MESSAGE_UPDATE
        else:
            response_type = hikari.ResponseType.DEFERRED_MESSAGE_CREATE
            
        await self.interaction.create_initial_response(response_type)  # type: ignore
        self.last_response = datetime.now()
        
        if update:
            self.change_state(DeferredUpdateResponseState)
        else:
            self.change_state(DeferredCreateResponseState)
        
        self._response_lock.release()



class CreatedResponseState(BaseResponseState):
    async def respond(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> None:
        # Implement the method
        pass

    async def edit(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
        message_id: Snowflake | None = None,
    ) -> None:
        # Implement the method
        pass

    async def defer(self, update: bool = False) -> None:
        # Implement the method
        pass

    @property
    def is_valid(self) -> bool:
        return (datetime.now() - self.last_response) < timedelta(minutes=15)



class DeferredCreateResponseState(BaseResponseState):
    async def respond(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> None:
        """Edits the initial response"""
        await self._response_lock.acquire()
        await self.interaction.edit_initial_response(
            content,
            embeds=embeds,
            components=components
        )

        async def delete_after_task(time: timedelta, interaction: ComponentInteraction | CommandInteraction):
            await asyncio.sleep(time.total_seconds())
            await interaction.delete_initial_response()
            self.change_state(DeletedResponseState)

        if delete_after:
            await asyncio.create_task(delete_after_task(delete_after, self.interaction))
        self._response_lock.release()
            
        

    async def edit(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
        message_id: Snowflake | None = None,
    ) -> None:
        """same as respond -> respond edits initial response"""
        await self.respond(
            embeds=embeds,
            content=content,
            components=components
        )

    async def defer(self, update: bool = False) -> None:
        """cannot be deferred again"""
        pass

    @property
    def is_valid(self) -> bool:
        # Implement the method
        return (datetime.now() - self.last_response) < timedelta(minutes=15)



class DeferredUpdateResponseState(DeferredCreateResponseState):
    """currently the same as DeferredCreateResponseState"""
    pass
    



class DeletedResponseState(BaseResponseState):
    async def respond(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> None:
        # Implement the method
        pass

    async def edit(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
        message_id: Snowflake | None = None,
    ) -> None:
        # Implement the method
        pass

    async def defer(self, update: bool = False) -> None:
        # Implement the method
        pass

    @property
    def is_valid(self) -> bool:
        # Implement the method
        return True