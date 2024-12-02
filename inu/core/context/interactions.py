import asyncio
from typing import *
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import functools
import attrs
import hikari
from hikari import (
    CacheAware, CommandInteraction, ComponentInteraction, GuildChannel, InteractionCreateEvent, ModalInteraction, PartialInteraction, RESTAware, ResponseType, 
    Snowflake, TextInputStyle, SnowflakeishOr, Embed
)
from hikari import embeds
from hikari.impl import MessageActionRowBuilder
from .._logging import getLogger
import lightbulb
from lightbulb import Context
from hikari import CommandInteractionOption

from ..bot import Inu
from . import (
    InuContextProtocol, UniqueContextInstance, Response, 
    BaseResponseState, InitialResponseState, Interaction
)

if TYPE_CHECKING:
    from .base import InuContextBase, InuContext

log = getLogger(__name__)





class BaseInteractionContext(InuContextBase, InuContext, AuthorMixin, CustomIDMixin):  # type: ignore[union-attr]
    def __init__(self, app: Inu, interaction: Interaction) -> None:
        super().__init__()
        self._interaction: Interaction = interaction
        self.update: bool = False
        self._response_lock: asyncio.Lock = asyncio.Lock()
        self._app = app
        self.response_state: BaseResponseState = InitialResponseState(
            self, self.interaction
        )

    @property
    def responses(self) -> List[Response]:
        return self._responses
    
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
        await self.response_state.respond(
            embeds=embeds,
            content=content,
            delete_after=delete_after,
            ephemeral=ephemeral,
            components=components
        )
        
    async def edit_last_response(self):
        ...

class CommandInteractionContext(BaseInteractionContext, AuthorMixin, GuildsAndChannelsMixin):  # type: ignore[union-attr]
    def __init__(self, app: Inu, interaction: hikari.CommandInteraction) -> None:
        super().__init__(app, interaction)
        
    
    
        