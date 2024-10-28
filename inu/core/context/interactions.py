import asyncio
from typing import *
from datetime import datetime, timedelta
import abc
import functools

import hikari
from hikari import CommandInteraction, ComponentInteraction, ResponseType, Snowflake, TextInputStyle, SnowflakeishOr
from hikari.impl import MessageActionRowBuilder
from .._logging import getLogger
import lightbulb
from lightbulb import Context
from hikari import CommandInteractionOption

from ..bot import Inu
from . import InuContext, InuContextProtocol, InuContextBase, UniqueContextInstance, Response

log = getLogger(__name__)


class BaseInteractionContext(InuContextBase, InuContext):
    def __init__(self, app: Inu, event: hikari.InteractionCreateEvent) -> None:
        super().__init__()
        self.event = event
        self.update: bool = False
        self._response_lock: asyncio.Lock = asyncio.Lock()
    
    @property
    def responses(self) -> List[Response]:
        return self._responses

    @property
    def interaction(self) -> CommandInteraction | ComponentInteraction:
        return self.event.interaction  # type: ignore
    
    @property    
    def channel_id(self) -> Snowflake:
        return self.interaction.channel_id
    
    @property
    def guild_id(self) -> Snowflake | None:
        return self.interaction.guild_id
    
    @property
    def last_response(self) -> Response | None:
        return self._responses[-1] if self._responses else None
    
    @property
    def first_response(self) -> Response | None:
        return self._responses[0] if self._responses else None
    
    async def respond(
        self, 
        embeds: List[hikari.Embed] | None = None,
        content: str | None = None,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: List[MessageActionRowBuilder] | None = None,   
    ):
        resp_id = await self.responses[0].respond(
            embeds=embeds,
            content=content,
            delete_after=delete_after,
            ephemeral=ephemeral,
            components=components
        )
        
    async def edit_last_response(self):
        ...
    
    
        