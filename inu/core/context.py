import asyncio
from typing import *
from datetime import datetime, timedelta

import hikari
from hikari import ComponentInteraction, ResponseType


REST_SENDING_MARGIN = 0.5 #seconds

class InteractionContext:
    """
    A wrapper for `hikari.ComponentInteraction`
    """
    def __init__(
        self, 
        interaction: ComponentInteraction, 
        ephemeral: bool = False,
        create: bool = True, 
        update: bool = False,
        deferr: bool = False,
        auto_deferr: bool = False,
        update_on_changes: bool = False,
    ):
        self._interaction = interaction
        self.responded = False
        self.message: hikari.Message
        self._ephemeral = ephemeral
        self._create = create
        self._upadate = update
        self._embeds: List[hikari.Embed] | None = None
        self._content: str | None = None
        self._update_on_changes: bool = update_on_changes
        self._extra_respond_kwargs: Dict[str, Any] = {}
        self._deferred: bool = False
        if deferr:
            asyncio.create_task(self._ack_interaction())
        if auto_deferr:
            asyncio.create_task(self._deferr_on_timelimit())

    async def _deferr_on_timelimit(self):
        respond_at = self.i.created_at + timedelta(seconds=(3 - REST_SENDING_MARGIN))   
        await asyncio.sleep(
            (respond_at - datetime.now()).total_seconds()
        )
        if not self.responded:
            await self._ack_interaction()


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
    def respond_kwargs(self) -> Dict[str, Any]:
        return self._extra_respond_kwargs

    @respond_kwargs.setter
    def respond_kwargs(self, value: Dict[str, Any]) -> None:
        self._extra_respond_kwargs = value

    
    async def execute(self, **kwargs) -> hikari.messages.Message:
        if not (old_state := self.responded):
            self.responded = True
        return await self.i.execute(**kwargs)
        if not old_state:
            self.message = await self.i.fetch_initial_response()
    @property
    def interaction_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {}
        if self.embeds:
            kwargs["embeds"] = self.embeds
        elif self.embed:
            kwargs["embeds"] = [self.embed]
        if self._content:
            kwargs["content"] = self._content

        resp_type: hikari.ResponseType | None = None
        if not self.responded and not self._deferred and self.is_valid:
            if self._create:
                resp_type = ResponseType.MESSAGE_CREATE
            if self._upadate:
                resp_type = ResponseType.MESSAGE_UPDATE
        if resp_type:
            kwargs["response_type"] = resp_type  #type: ignore
        return kwargs

    @property
    def user(self) -> hikari.User:
        return self.i.user

    @property
    def created_at(self) -> datetime:
        return self.i.created_at

    @property
    def channel_id(self) -> hikari.Snowflake:
        return self.i.channel_id

    @property
    def guild_id(self) -> hikari.Snowflake | None:
        return self.i.guild_id

    @property
    def custom_id(self) -> str:
        return self.i.custom_id

    @property
    def values(self) -> List[str]:
        return self.i.values

    @property
    def is_valid(self) -> bool:
        return datetime.now() < (self.created_at + timedelta(minutes=15))

    async def respond(self, update: bool = False, **kwargs) -> None | hikari.Message:
        if not self.is_valid:
            if self._upadate:
                return await self.i.app.rest.edit_message(
                    channel=self.channel_id,
                    message=self.message.id,
                    **self.interaction_kwargs, 
                    **self._extra_respond_kwargs,
                    **kwargs
                )
            else:
                self.i.app.rest.create_message(
                    channel=self.channel_id,
                    **self.interaction_kwargs, 
                    **self._extra_respond_kwargs,
                    **kwargs
                )
        if not self.responded:
            self.responded = True
            await self.i.create_initial_response(**self.interaction_kwargs, **self._extra_respond_kwargs, **kwargs)
            self.message = await self.i.fetch_initial_response()
            return None
        if update:
            await self.i.edit_initial_response(**self.interaction_kwargs, **self._extra_respond_kwargs, **kwargs)
            return None
        else:
            return await self.execute(**kwargs)

            


InteractionContext.execute.__doc__ = hikari.ComponentInteraction.execute.__doc__

    