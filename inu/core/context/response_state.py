import asyncio
import abc
from typing import *
from datetime import datetime, timedelta
from xml.etree.ElementPath import prepare_parent

import hikari
from hikari import COMMAND_RESPONSE_TYPES, Embed, ComponentInteraction, CommandInteraction, InteractionCreateEvent, Message, ResponseType, Snowflake, SnowflakeishOr, WebhookChannelT
from hikari.api import Response
from hikari.impl import MessageActionRowBuilder
from datetime import timedelta

#from . import Response
from core import getLogger
from .response_proxy import InitialResponseProxy, ResponseProxy, WebhookProxy
if TYPE_CHECKING:
    from .base import InuContextBase



# TODO: CreatedState -> DeletedState: Transfer .responses


class BaseResponseState(abc.ABC):
    interaction: CommandInteraction | ComponentInteraction
    responses: List[ResponseProxy]
    context: 'InuContextBase'
    last_response: datetime

    def __init__(
        self, 
        interaction: ComponentInteraction | CommandInteraction, 
        context: 'InuContextBase',
        responses: List[ResponseProxy]
    ) -> None:
        self.interaction = interaction
        self._deferred: bool = False
        self._responded: bool = False
        self._response_lock: asyncio.Lock = asyncio.Lock()
        self.last_response: datetime = self.created_at
        self.responses = responses
        self.context = context
        self.log = getLogger(__name__, self.__class__.__name__)
        
    def change_state(self, new_state: Type["BaseResponseState"]):
            """
            Changes the ResponseState of the parent `InuContextBase` to the new state, coping `interaction` and `context`
            """
            state = new_state(
                self.interaction,
                self.context,
                self.responses
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
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE,
        update: bool = False,
    ) -> ResponseProxy:
        ...
    
    async def execute(
        self,
        content: str,
        embeds: List[hikari.Embed] | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> hikari.Message:
        return await self.interaction.execute(
            content,
            embeds=embeds or [],
            components=components or []
        )
    
    async def edit_last_response(
        self,
        embeds: List[hikari.Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> hikari.Message:
        if len(self.responses) > 0:
            return await self.interaction.edit_message(
                await self.responses[-1].message(),
                embeds=embeds,
                content=content,
                components=components
            )
        else:
            return await self.interaction.edit_initial_response(
                content=content,
                embeds=embeds,
                components=components
            )

    async def delete_webhook_message(self, message: SnowflakeishOr[Message]) -> None:
        await self.interaction.delete_message(message)

    @abc.abstractmethod
    async def edit(
        self,
        embeds: List[hikari.Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
        message_id: Snowflake | None = None,
        **kwargs: Dict[str, Any]
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

    async def delete_initial_response(self) -> None:
        await self.interaction.delete_initial_response()
        
        
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
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE,
        update: bool = False,
    ) -> ResponseProxy:
        await self._response_lock.acquire()
        
        if self._responded or self._deferred:
            raise RuntimeError(f"can't create a response in {type(self)} when alreaded responded or deferred")
        
        kwargs = {
            'embeds': embeds,
            'content': content,
            'components': components,
            'flags': flags,
            'delete_after': delete_after,
        }
        kwargs["flags"] = hikari.MessageFlag.NONE
        if ephemeral:
            kwargs["flags"] = hikari.MessageFlag.EPHEMERAL
            
        if update:
            self.log.debug("updating last response")
            self._response_lock.release()
            await self.edit(**kwargs)
            return self.responses[-1]
        
        self.log.debug(f"creating initial response with args: {kwargs=}")

        
        kwargs.pop('delete_after')
        await self.interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            **kwargs
        )
        self.responses.append(InitialResponseProxy(interaction=self.interaction))
        self.last_response = datetime.now()
        self.change_state(CreatedResponseState)
        self._response_lock.release()
        return self.responses[-1]
        
    async def edit(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
        message_id: Snowflake | None = None,
        **kwargs: Dict[str, Any]
    ) -> None:
        """
        Initial Response with MESSAGE_UPDATE

        change state -> CreatedResponseState
        """
        await self._response_lock.acquire()
        await self.interaction.create_initial_response(
            ResponseType.MESSAGE_UPDATE, content,  # type: ignore
            embeds=embeds,
            components=components,
        )
        self.last_response = datetime.now()
        self.responses.append(InitialResponseProxy(interaction=self.interaction))
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
        
        # if update:
        #     self.change_state(DeferredUpdateResponseState)
        # else:
        self.change_state(DeferredCreateResponseState)
        
        self._response_lock.release()



class CreatedResponseState(BaseResponseState):
    """
    State when the initial response has been created
    """
    async def respond(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: List[MessageActionRowBuilder] | None = None,
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE,
        update: bool = False,
    ) -> ResponseProxy:
        await self._response_lock.acquire()

        if update:
            # call edit_last_response instead
            self.log.debug("updating last response")
            await self.edit_last_response(
                embeds=embeds,
                content=content,
                components=components
            )
            self._response_lock.release()
            return self.responses[-1]

        self.log.debug("creating followup message")
        message = await self.interaction.execute(
            content,
            embeds=embeds or [],
            components=components or [],
            flags=flags
        )
        self.responses.append(WebhookProxy(message, self.interaction))
        

        async def delete_after_task(time: timedelta, interaction: ComponentInteraction | CommandInteraction):
            await asyncio.sleep(time.total_seconds())
            await interaction.delete_message(message)
            self.change_state(DeletedResponseState)

        if delete_after:
            await asyncio.create_task(delete_after_task(delete_after, self.interaction))
        self._response_lock.release()
        return self.responses[-1]
        

    async def edit(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
        message_id: Snowflake | None = None,
        **kwargs: Dict[str, Any]
    ) -> None:
        await self._response_lock.acquire()
        if message_id is None:
            _message = await self.interaction.edit_initial_response(
                content,
                embeds=embeds,
                components=components
            )
        else:
            _message = await self.interaction.edit_message(
                message_id,
                content,
                embeds=embeds,
                components=components
            )
        self._response_lock.release()

    async def defer(self, update: bool = False) -> None:
        """Cannot be deferred again"""
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
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE,
        update: bool = False,
    ) -> ResponseProxy:
        """Edits the initial response
        
        Notes:
        -----
        flags will be ignored here
        """
        # update is ignored here, since deferred message needs to be updated anyways
        await self._response_lock.acquire()
        self.log.debug("updating (ignoring update) deferred initial response")
        message = await self.interaction.edit_initial_response(
            content,
            embeds=embeds,
            components=components,
        )
        self.responses.append(InitialResponseProxy(interaction=self.interaction))

        async def delete_after_task(time: timedelta, interaction: ComponentInteraction | CommandInteraction):
            await asyncio.sleep(time.total_seconds())
            await interaction.delete_initial_response()
            self.change_state(DeletedResponseState)

        if delete_after:
            await asyncio.create_task(delete_after_task(delete_after, self.interaction))
        self._response_lock.release()
        return self.responses[-1]
            
        

    async def edit(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
        message_id: Snowflake | None = None,
        **kwargs: Dict[str, Any]
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
        return (datetime.now() - self.last_response) < timedelta(minutes=15)



# class DeferredUpdateResponseState(DeferredCreateResponseState):
#     """currently the same as DeferredCreateResponseState"""
#     pass
    



class DeletedResponseState(BaseResponseState):
    async def respond(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: List[MessageActionRowBuilder] | None = None,
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE,
        update: bool = False,
    ) -> ResponseProxy:
        """
        Creates a Followup message
        """
        kwargs = {}
        if content:
            kwargs['content'] = content
        if embeds:
            kwargs['embeds'] = embeds
        if components:
            kwargs['components'] = components

        if update:
            await self.edit_last_response(**kwargs)
            return self.responses[-1]

        msg = await self.interaction.execute(**kwargs, flags=flags)
        self.responses.append(WebhookProxy(msg, self.interaction))
        return self.responses[-1]

    async def edit(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
        message_id: Snowflake | None = None,
        **kwargs: Dict[str, Any]
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