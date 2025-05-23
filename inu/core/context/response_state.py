import asyncio
import abc
from contextlib import suppress
import traceback
from typing import *
from datetime import datetime, timedelta
from xml.etree.ElementPath import prepare_parent

import hikari
from hikari import (COMMAND_RESPONSE_TYPES, Embed, ComponentInteraction, 
    CommandInteraction, InteractionCreateEvent, Message, ResponseType, 
    Snowflake, SnowflakeishOr, WebhookChannelT, UndefinedOr, UNDEFINED, 
    UndefinedNoneOr, Resourceish
)
from hikari.api import Response
from hikari.impl import MessageActionRowBuilder
from datetime import timedelta

from pytz import utc

#from . import Response
from core import getLogger
from .response_proxy import InitialResponseProxy, ResponseProxy, RestResponseProxy, WebhookProxy
if TYPE_CHECKING:
    from . import InuContext
    from .base import InuContextBase



# TODO: CreatedState -> DeletedState: Transfer .responses

log = getLogger(__name__)

class BaseResponseState(abc.ABC):
    _interaction: CommandInteraction | ComponentInteraction | None
    responses: List[ResponseProxy]
    context: 'InuContextBase'
    _last_response: datetime

    def __init__(
        self, 
        interaction: ComponentInteraction | CommandInteraction | None, 
        context: 'InuContextBase',
        responses: List[ResponseProxy]
    ) -> None:
        self._interaction = interaction
        self._deferred: bool = False
        self._responded: bool = False
        self._response_lock: asyncio.Lock = asyncio.Lock()
        self._last_response: datetime = self.created_at
        log.debug(f"{self._last_response=}")
        self._invalid_task = asyncio.create_task(self.trigger_transition_when_invalid())
        self.responses = responses
        self.context = context
        self.log = getLogger(__name__, self.__class__.__name__)

    @property
    @abc.abstractmethod
    def invalid_at(self) -> datetime:
        ...
    
    @property
    def invalid_at_relative(self) -> timedelta:
        return self.invalid_at - datetime.now(utc)
    
    @property
    def interaction(self) -> CommandInteraction | ComponentInteraction:
        assert(isinstance(self._interaction, (CommandInteraction, ComponentInteraction)))
        return self._interaction

    def change_state(self, new_state: Type["BaseResponseState"]):
            """
            Changes the ResponseState of the parent `InuContextBase` to the new state, coping `interaction` and `context`
            """
            try:
                log.debug(f"changing state from {type(self).__name__} to {new_state.__name__}")
                if self._invalid_task is not None:
                    self._invalid_task.cancel()
                state = new_state(
                    self.interaction,
                    self.context,
                    self.responses
                )
                self.context.set_response_state(state)
            except Exception as e:
                log.error(f"Error changing state: {traceback.format_exc()}")
    
    def filter_responses(self, predicate: Callable[[ResponseProxy], bool]) -> List[ResponseProxy]:
        return [response for response in self.responses if predicate(response)]
    
    @property
    def last_response(self) -> datetime:
        """
        returns the maximum datetime out of all interaction responses and the interaction
        """
        interaction_responses = self.filter_responses(lambda x: isinstance(x, (WebhookProxy, InitialResponseProxy)))
        datetimes = [i.created_at for i in interaction_responses]
        return max([*datetimes, self._last_response])

    @abc.abstractmethod
    async def respond(
        self,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE,
        update: SnowflakeishOr[Message] | bool = False,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,  # added argument
    ) -> ResponseProxy:
        ...
    
    async def execute(
        self,
        content: UndefinedOr[str] = UNDEFINED,
        embed: UndefinedNoneOr[Embed] = UNDEFINED,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        delete_after: timedelta | None = None,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,   
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,
    ) -> hikari.Message:
        # Handle single embed case
        if embed is not UNDEFINED and embeds is UNDEFINED:
            embeds = [embed] if embed else []
        
        # Execute the message
        message = await self.interaction.execute(
            content,
            embeds=embeds or [],
            components=components or [],
            attachments=attachments or [],
        )

        # Create proxy and add to responses
        proxy = WebhookProxy(message, self.interaction)
        self.responses.append(proxy)

        # Handle delete_after if specified
        if delete_after is not None:
            asyncio.create_task(proxy.delete_after(delete_after))

        return message
    
    async def edit_last_response(
        self,
        embeds: UndefinedOr[List[hikari.Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,  # added argument
    ) -> hikari.Message:
        if len(self.responses) > 0:
            return await self.interaction.edit_message(
                await self.responses[-1].message(),
                embeds=embeds,
                content=content,
                components=components,
                attachments=attachments,  # added argument
            )
        else:
            return await self.interaction.edit_initial_response(
                content=content,
                embeds=embeds,
                components=components,
                attachments=attachments,  # added argument
            )

    async def delete_webhook_message(self, message: SnowflakeishOr[Message]) -> None:
        await self.interaction.delete_message(message)

    @abc.abstractmethod
    async def edit(
        self,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        message_id: SnowflakeishOr[Message] | bool | None = None,
        attachment: UndefinedNoneOr[Resourceish] = UNDEFINED,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,
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

    async def trigger_transition_when_invalid(self):
        """
        Triggers a transition to the RestResponseState when the current response becomes invalid.

        This method continuously monitors the validity of the current response. When the response
        becomes invalid (typically after 15 minutes), it transitions to the RestResponseState.

        The method sleeps until the expected invalidation time to avoid unnecessary CPU usage.

        Returns
        -------
        None
        """
        while self.is_valid and self.invalid_at_relative > timedelta(seconds=0):
            probably_invalid_in = self.invalid_at_relative + timedelta(seconds=1)
            log.debug(f"sleep until {self.invalid_at} when response invalidates (in {probably_invalid_in})")
            await asyncio.sleep(probably_invalid_in.total_seconds())
        log.debug(f"response is invalid, transitioning to RestResponseState; {self.last_response=}, {datetime.now(utc)=}")
        self._invalid_task = None
        self.change_state(RestResponseState)
        
class InitialResponseState(BaseResponseState):

    @property
    def invalid_at(self) -> datetime:
        return self.created_at + timedelta(minutes=3)
    
    @property
    def is_valid(self) -> bool:
        log.debug(f"{(datetime.now(utc) - self.last_response) < timedelta(minutes=3)} - {datetime.now(utc) - self.last_response}")
        return (datetime.now(utc) - self.last_response) < timedelta(minutes=3) 
        # theoretically 3sec, but often timeserver is too inaccurate
    
    async def respond(
        self,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE,
        update: SnowflakeishOr[Message] | bool = False,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,  # added argument
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
            'attachments': attachments,  # added argument
        }
        kwargs["flags"] = hikari.MessageFlag.NONE
        if ephemeral:
            kwargs["flags"] = hikari.MessageFlag.EPHEMERAL
            
        if update:
            self.log.debug("updating last response")
            self._response_lock.release()
            await self.edit(**kwargs)
            return self.responses[-1]
        
        self.log.trace(f"creating initial response with args: {kwargs=}")

        
        kwargs.pop('delete_after')
        await self.interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            **kwargs
        )
        self.responses.append(InitialResponseProxy(interaction=self.interaction))
        # self.last_response = datetime.now()
        self.change_state(CreatedResponseState)
        self._response_lock.release()
        return self.responses[-1]
        
    async def edit(
        self,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        message_id: SnowflakeishOr[Message] | bool | None = None,
        attachment: UndefinedNoneOr[Resourceish] = UNDEFINED,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,
        **kwargs: Dict[str, Any]
    ) -> None:
        """
        Initial Response with MESSAGE_UPDATE

        change state -> CreatedResponseState
        """
        await self._response_lock.acquire()
        if not attachment in [UNDEFINED, None] and not attachments:
            attachments = [attachment]  # type: ignore
        log.debug(f"editing initial response with {embeds=}, {content=}, {components=}")
        await self.interaction.create_initial_response(
            ResponseType.MESSAGE_UPDATE, content,  # type: ignore
            embeds=embeds,
            components=components,
            attachments=attachments
        )
        # self.last_response = datetime.now()
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
        self._last_response = datetime.now(utc)
        
        # if update:
        #     self.change_state(DeferredUpdateResponseState)
        # else:
        self.change_state(DeferredCreateResponseState)
        
        self._response_lock.release()



class CreatedResponseState(BaseResponseState):
    """
    State when the initial response has been created
    """
    @property
    def invalid_at(self) -> datetime:
        return self.created_at + timedelta(minutes=14)
    
    async def respond(
        self,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE,
        update: SnowflakeishOr[Message] | bool = False,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,  # added argument
    ) -> ResponseProxy:
        await self._response_lock.acquire()

        if update:
            # call edit_last_response instead
            await self.edit_last_response(
                embeds=embeds,
                content=content,
                components=components,
                attachments=attachments
            )
            self._response_lock.release()
            return self.responses[-1]

        self.log.debug("creating followup message")
        message = await self.interaction.execute(
            content,
            embeds=embeds or [],
            components=components or [],
            flags=flags,
            attachments=attachments,  # added argument
        )
        self.responses.append(WebhookProxy(message, self.interaction))
        

        async def delete_after_task(time: timedelta | float, interaction: ComponentInteraction | CommandInteraction):
            if isinstance(time, timedelta):
                time = time.total_seconds()
            await asyncio.sleep(time)
            await interaction.delete_message(message)
            self.change_state(DeletedResponseState)

        if delete_after:
            await asyncio.create_task(delete_after_task(delete_after, self.interaction))
        self._response_lock.release()
        return self.responses[-1]
        

    async def edit(
        self,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        message_id: SnowflakeishOr[Message] | bool | None = None,
        attachment: UndefinedNoneOr[Resourceish] = UNDEFINED,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,
        **kwargs: Dict[str, Any]
    ) -> None:
        await self._response_lock.acquire()
        if message_id is None:
            _message = await self.interaction.edit_initial_response(
                content,
                embeds=embeds,
                components=components,
                attachment=attachment,
                attachments=attachments
            )
        else:
            _message = await self.interaction.edit_message(
                message_id,
                content,
                embeds=embeds,
                components=components,
                attachment=attachment,
                attachments=attachments
            )
        self._response_lock.release()

    async def defer(self, update: bool = False) -> None:
        """Cannot be deferred again"""
        pass

    @property
    def is_valid(self) -> bool:
        return (datetime.now(utc) - self.created_at) < timedelta(minutes=15)



class DeferredCreateResponseState(BaseResponseState):
    @property
    def invalid_at(self) -> datetime:
        return self.created_at + timedelta(minutes=14)
    
    async def respond(
        self,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE,
        update: SnowflakeishOr[Message] | bool = False,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,  # added argument
    ) -> ResponseProxy:
        """Edits the initial response
        
        Notes:
        -----
        flags will be ignored here
        """
        # update is ignored here, since deferred message needs to be updated anyways
        await self._response_lock.acquire()
        self.log.debug("updating (ignoring update) deferred initial response")
        self.log.debug(f"responding with {embeds=}, {content=}, {components=}, {attachments=}")
        message = await self.interaction.edit_initial_response(
            content,
            embeds=embeds,
            components=components,
            attachments=attachments,  # added argument
        )
        self.responses.append(InitialResponseProxy(interaction=self.interaction))

        async def delete_after_task(time: timedelta, interaction: ComponentInteraction | CommandInteraction):
            await asyncio.sleep(time.total_seconds())
            await interaction.delete_initial_response()
            self.change_state(DeletedResponseState)

        if delete_after:
            await asyncio.create_task(delete_after_task(delete_after, self.interaction))
        self.change_state(CreatedResponseState)
        self._response_lock.release()
        return self.responses[-1]

    async def edit(
        self,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        message_id: SnowflakeishOr[Message] | bool | None = None,
        attachment: UndefinedNoneOr[Resourceish] = UNDEFINED,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,
        **kwargs: Dict[str, Any]
    ) -> None:
        """same as respond -> respond edits initial response"""
        if not attachment in [UNDEFINED, None] and not attachments:
            attachments = [attachment]  # type: ignore
        await self.respond(
            embeds=embeds,
            content=content,
            components=components,
            attachments=attachments,
        )

    async def defer(self, update: bool = False) -> None:
        """cannot be deferred again"""
        pass

    @property
    def is_valid(self) -> bool:
        return (datetime.now(utc) - self.last_response) < timedelta(minutes=15)
    



class DeletedResponseState(BaseResponseState):
    @property
    def invalid_at(self) -> datetime:
        return self.created_at + timedelta(minutes=14)
    
    async def respond(
        self,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE,
        update: SnowflakeishOr[Message] | bool = False,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,  # added argument
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
        kwargs['attachments'] = attachments  # added argument

        if update:
            await self.edit_last_response(**kwargs)
            return self.responses[-1]

        msg = await self.interaction.execute(**kwargs, flags=flags)
        self.responses.append(WebhookProxy(msg, self.interaction))
        return self.responses[-1]

    async def edit(
        self,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        message_id: SnowflakeishOr[Message] | bool | None = None,
        attachment: UndefinedNoneOr[Resourceish] = UNDEFINED,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,
        **kwargs: Dict[str, Any]
    ) -> None:
        await self._response_lock.acquire()
        if message_id is None:
            raise RuntimeError("Cannot edit deleted initial response. Consider passing a message_id")
        _message = await self.interaction.edit_message(
            message_id,
            content,
            embeds=embeds,
            components=components,
            attachment=attachment,
            attachments=attachments
        )
        self._response_lock.release()

    async def defer(self, update: bool = False) -> None:
        return 

    @property
    def is_valid(self) -> bool:
        return (datetime.now(utc) - self.last_response) < timedelta(minutes=15)



class RestResponseState(BaseResponseState):
    def __init__(
        self, 
        interaction: ComponentInteraction | CommandInteraction | None, 
        context: 'InuContextBase',
        responses: List[ResponseProxy],
        message: Optional[Message] = None
    ) -> None:
        self._message = message
        self._instanciated_at = datetime.now(utc)
        self._interaction = interaction
        self._deferred: bool = False
        self._responded: bool = False
        self._response_lock: asyncio.Lock = asyncio.Lock()
        self._last_response: datetime = self.created_at
        
        self._invalid_task = None  # can't get invalid
        self.responses = responses
        self.context = context
        self.log = getLogger(__name__, self.__class__.__name__)

    @property
    def invalid_at(self) -> datetime:
        return self.created_at + timedelta(days=999)
    
    async def respond(
        self,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE,
        update: SnowflakeishOr[Message] | bool = False,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,  # added argument
    ) -> ResponseProxy:
        """Edits the initial response
        
        Notes:
        -----
        flags will be ignored here
        """
        await self._response_lock.acquire()
        
        if update != False:
            log.debug(f"redirect from respond to edit")
            # call edit instead
            await self.edit(
                embeds=embeds,
                content=content,
                components=components,
                attachments=attachments,
                message_id=update
            )
            self._response_lock.release()
            return self.responses[-1]

        context = cast("InuContext", self.context)
        log.debug(f"make response with {embeds=}, {content=}, {components=} {embeds=} {attachments=}" )
        message = await self.context._bot.rest.create_message(
            context.channel_id,
            content,
            embeds=embeds or [],
            components=components or [],
            attachments=attachments,  # added argument
        )
        proxy = RestResponseProxy(message=message)
        self.responses.append(proxy)

        async def delete_after_task(time: timedelta):
            await asyncio.sleep(time.total_seconds())
            await message.delete()
            self.responses.remove(proxy)
            self.change_state(DeletedResponseState)

        if delete_after:
            await asyncio.create_task(delete_after_task(delete_after))
        self._response_lock.release()
        return self.responses[-1]
        
    async def edit(
        self,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
        message_id: SnowflakeishOr[Message] | bool | None = None,
        attachment: UndefinedNoneOr[Resourceish] = UNDEFINED,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,
        **kwargs: Dict[str, Any]
    ) -> None:
        """same as respond -> respond edits initial response"""
        if isinstance(message_id, bool):
            message_id = None
        
        message_extras = {
            'embeds': embeds,
            'components': components,
            'attachment': attachment,
            'attachments': attachments
        }
        if not (self.responses or message_id):
            # make normal response when update is not possible
            log.debug(f"redirect from edit to response")
            await self.respond(content=content, **message_extras)
            return
        # edit given message or last response
        context = cast("InuContext", self.context)
        given_or_last = message_id or (await self.responses[-1].message()).id
        log.debug(f"editing message {given_or_last}")
        message = await context.bot.rest.edit_message(
            context.channel_id,
            given_or_last,
            content,
            **message_extras
        )
        self.responses.append(RestResponseProxy(message=message))

    async def defer(self, update: bool = False) -> None:
        """cannot be deferred again"""
        pass

    @property
    def created_at(self) -> datetime:
        if self._message is not None:
            return self._message.created_at
        return self._instanciated_at

    @property
    def is_valid(self) -> bool:
        return True
    
    async def trigger_transition_when_invalid(self):
        # does not exist in RestResponseState
        pass