import asyncio
import abc
from typing import *
from datetime import datetime, timedelta

import hikari
from hikari import Embed, ComponentInteraction, CommandInteraction, InteractionCreateEvent, Message, Snowflake
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
    
    
class BaseResponseState(abc.ABC):
    interaction: CommandInteraction | ComponentInteraction
    webhooks: List[Message]
    context: 'InuContextBase'
    embeds: List[hikari.Embed] | None
    content: str | None
    delete_after: timedelta | None
    components: List[MessageActionRowBuilder] | None
    ephemeral: bool
    
    def __init__(
        self,
        interaction: CommandInteraction | ComponentInteraction,
        context: 'InuContextBase'
    ) -> None:
        self.interaction = interaction
        self.context = context
        
    
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
        embeds = embeds or self.embeds
        content = content or self.content
        components = components or self.components
        
        await self.interaction.edit_message(
            self.webhooks[-1],
            embeds=embeds,
            content=content,
            components=components
        )
        
    @abc.abstractmethod
    async def edit(
        self,
        message_id: Snowflake,
        embeds: List[hikari.Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ):
        ...
        
    @abc.abstractmethod
    async def defer(self, update: bool = False) -> None:
        ...
        
    @property
    def created_at(self) -> datetime:
        return self.interaction.created_at
    
    @abc.abstractmethod
    def is_valid(self) -> bool:
        ...
        
        
class InitialResponseState(BaseResponseState):
    def __init__(
        self, 
        interaction: ComponentInteraction | CommandInteraction, 
        context: 'InuContextBase'
    ) -> None:
        super().__init__(interaction, context)
        self._deferred: bool = False
        self._responded: bool = False
        self._response_lock: asyncio.Lock = asyncio.Lock()
        
    
    def change_state(self, new_state: Type[BaseResponseState]):
        """Changes the ResponseState of the context"""
        state = new_state(
            self.interaction,
            self.context
        )
        self.context.set_response_state(state)
        
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
        self.change_state(CreatedResponseState)
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
        message_id: Snowflake,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> None:
        # Implement the method
        pass

    async def defer(self, update: bool = False) -> None:
        # Implement the method
        pass

    def is_valid(self) -> bool:
        # Implement the method
        return True

class UpdatedResponseState(BaseResponseState):
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
        message_id: Snowflake,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> None:
        # Implement the method
        pass

    async def defer(self, update: bool = False) -> None:
        # Implement the method
        pass

    def is_valid(self) -> bool:
        # Implement the method
        return True

class FinishedResponseState(BaseResponseState):
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
        message_id: Snowflake,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> None:
        # Implement the method
        pass

    async def defer(self, update: bool = False) -> None:
        # Implement the method
        pass

    def is_valid(self) -> bool:
        # Implement the method
        return True

class DeferredCreateResponseState(FinishedResponseState):
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
        message_id: Snowflake,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> None:
        # Implement the method
        pass

    async def defer(self, update: bool = False) -> None:
        # Implement the method
        pass

    def is_valid(self) -> bool:
        # Implement the method
        return True

class DeferredUpdateResponseState(FinishedResponseState):
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
        message_id: Snowflake,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> None:
        # Implement the method
        pass

    async def defer(self, update: bool = False) -> None:
        # Implement the method
        pass

    def is_valid(self) -> bool:
        # Implement the method
        return True
