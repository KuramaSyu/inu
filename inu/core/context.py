import asyncio
from typing import *
from datetime import datetime, timedelta

import hikari
from hikari import ComponentInteraction, ResponseType
from ._logging import getLogger

log = getLogger(__name__)


REST_SENDING_MARGIN = 0.5 #seconds

class InteractionContext:
    """
    A wrapper for `hikari.ComponentInteraction`
    """
    def __init__(
        self, 
        interaction: ComponentInteraction, 
        ephemeral: bool = False,
        update: bool = False,
        deferr: bool = False,
        auto_deferr: bool = False,
        update_on_changes: bool = False,
    ):
        self._interaction = interaction
        self.responded = False
        self.message: hikari.Message | None = None
        self._ephemeral = ephemeral
        self._create = not update
        self._upadate = update
        self._embeds: List[hikari.Embed] | None = None
        self._content: str | None = None
        self._update_on_changes: bool = update_on_changes
        self._extra_respond_kwargs: Dict[str, Any] = {}
        self._deferred: bool = False
        self._parent_message: hikari.Message | None = None
        if deferr:
            asyncio.create_task(self._ack_interaction())
        if auto_deferr:
            asyncio.create_task(self._deferr_on_timelimit())

    async def _deferr_on_timelimit(self):
        respond_at = self.i.created_at + timedelta(seconds=(3 - REST_SENDING_MARGIN))  
        respond_at = respond_at.replace(tzinfo=None)
        await asyncio.sleep(
            (respond_at - datetime.utcnow()).total_seconds()
        )
        if not self.responded:
            await self._ack_interaction()

    async def fetch_parent_message(self):
        self.i.delete
        if not self._parent_message:
            self._parent_message = await self.i.fetch_parent_message()

    async def _ack_interaction(self):
        if self._upadate:
            await self.i.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
        else:
            await self.i.create_initial_response(ResponseType.DEFERRED_MESSAGE_CREATE)
        self._deferred = True
    
    @property
    def embed(self) -> hikari.Embed | None:
        if not self._embeds:
            return None
        return self._embeds[0]

    @embed.setter
    def embed(self, embed: hikari.Embed) -> None:
        if not self._embeds:
            self._embeds = []
        self._embeds[0] = embed

    @property
    def embeds(self) -> List[hikari.Embed] | None:
        return self._embeds

    @embeds.setter
    def embeds(self, embeds: List[hikari.Embed]) -> None:
        self._embeds = embeds

    @property
    def i(self) -> hikari.ComponentInteraction | hikari.CommandInteraction:
        return self._interaction

    @property
    def author(self) -> hikari.User:
        return self.i.user

    @property
    def respond_kwargs(self) -> Dict[str, Any]:
        return self._extra_respond_kwargs

    @respond_kwargs.setter
    def respond_kwargs(self, value: Dict[str, Any]) -> None:
        self._extra_respond_kwargs = value

    async def delete_initial_response(self, after: int | None = None):
        if after:
            await asyncio.sleep(after)
        return await self.i.delete_initial_response()

    async def delete_webhook_message(self, message: int | hikari.Message, after: int | None = None):
        if after:
            await asyncio.sleep(after)
        return await self.i.delete_message(message)
    
    async def execute(self, delete_after: int | None = None, ensure_return: bool = False, **kwargs) -> hikari.messages.Message | None:
        if not self.responded:
            # make inital response instead
            await self.respond(**kwargs)
            if delete_after:
                # start delete timeer
                asyncio.create_task(self.delete_initial_response(after=delete_after))
            if ensure_return:
                # ensure, that a message and not None is returned
                return await self.i.fetch_initial_response()
        else:
            # initial response was made -> actually execute the webhook
            msg = await self.i.execute(**kwargs)
            if delete_after:
                # start delete timer
                asyncio.create_task(self.delete_webhook_message(msg, after=delete_after))
            return msg

    def interaction_kwargs(self, with_response_type: bool = False, update: bool = False) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {}
        if self.embeds:
            kwargs["embeds"] = self.embeds
        elif self.embed:
            kwargs["embeds"] = [self.embed]
        if self._content:
            kwargs["content"] = self._content

        if with_response_type or (not self.responded and not self._deferred and self.is_valid):
            if self._upadate or update:
                kwargs["response_type"] = ResponseType.MESSAGE_UPDATE
            else:
                kwargs["response_type"] = ResponseType.MESSAGE_CREATE
        print(f"{kwargs =}")
        return kwargs

    @property
    def user(self) -> hikari.User:
        return self.i.user

    @property
    def user_id(self) -> hikari.Snowflake:
        return self.user.id

    @property
    def created_at(self) -> datetime:
        return self.i.created_at.replace(tzinfo=None)

    @property
    def channel_id(self) -> hikari.Snowflake:
        return self.i.channel_id

    @property
    def guild_id(self) -> hikari.Snowflake | None:
        return self.i.guild_id

    @property
    def custom_id(self) -> str:
        # if isinstance(self.i, hikari.CommandInteraction):
        #     raise RuntimeError(f"type {type(self.i)} has no attribute custom_id")
        return self.i.custom_id

    @property
    def message_id(self) -> int:
        # if isinstance(self.i, hikari.CommandInteraction):
        #     raise RuntimeError(f"type {type(self.i)} has no attribute message_id")
        return self.i.message.id

    @property
    def values(self) -> List[str]:
        return self.i.values

    @property
    def is_valid(self) -> bool:
        return datetime.now() < (self.created_at + timedelta(minutes=15))

    async def respond(self, update: bool = False, **kwargs) -> None | hikari.Message:
        if not self.is_valid:
            # webhook is unvalid due to older than 15 min
            print("unvalid")
            if update:
                # update message with REST call
                if not self.message:
                    raise RuntimeError("Can't update message. `message` attr is None")
                return await self.i.app.rest.edit_message(
                    channel=self.channel_id,
                    message=self.message.id,
                    **self.interaction_kwargs(), 
                    **self._extra_respond_kwargs,
                    **kwargs
                )
            else:
                # create message with REST call
                self.message = await self.i.app.rest.create_message(
                    channel=self.channel_id,
                    **self.interaction_kwargs(), 
                    **self._extra_respond_kwargs,
                    **kwargs
                )
                return self.message
        if not self.responded:
            # webhook is valid
            # make initial response
            self.responded = True
            print(f"create {update=}")
            await self.i.create_initial_response(
                **self.interaction_kwargs(with_response_type=True, update=update), 
                **self._extra_respond_kwargs, 
                **kwargs
            )
            asyncio.create_task(self._cache_initial_response())
            return None
        if update:
            # webhook is valid
            # inital response was already made
            # update existing inital response
            print("update")
            await self.i.edit_initial_response(
                **self.interaction_kwargs(), 
                **self._extra_respond_kwargs, 
                **kwargs
            )
            # cache message
            asyncio.create_task(self._cache_initial_response())
            return None
        else:
            # webhook is valid
            # inital response was made
            # update is False
            # -> execute webhook
            print("execute")
            return await self.execute(**kwargs)

    async def initial_response_create(self, **kwargs):
        if not self._deferred:
            await self.i.create_initial_response(
                response_type=ResponseType.MESSAGE_CREATE, 
                **self._extra_respond_kwargs, 
                **kwargs
            )
        else:
            await self.i.edit_initial_response(
                **self._extra_respond_kwargs, 
                **kwargs
            )
        self.responded = True
        asyncio.create_task(self._cache_initial_response())
    
    async def _cache_initial_response(self) -> None:
        self.message = await self.i.fetch_initial_response()

    async def fetch_response(self):
        """message from initial response or the last execute"""
        if not self.message:
            await self._cache_initial_response()
        return self.message

    async def initial_response_update(self, **kwargs):
        if not self._deferred:
            await self.i.create_initial_response(
                response_type=ResponseType.MESSAGE_UPDATE, 
                **self._extra_respond_kwargs, 
                **kwargs
            )
        else:
            await self.i.edit_initial_response(
                **self._extra_respond_kwargs, 
                **kwargs
            )
        self.responded = True
        asyncio.create_task(self._cache_initial_response())

            


InteractionContext.execute.__doc__ = hikari.ComponentInteraction.execute.__doc__

    