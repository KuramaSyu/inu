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
    BaseResponseState, InitialResponseState, Interaction,
    GuildsAndChannelsMixin, AuthorMixin, CustomIDMixin
)
from .base import InuContextBase, InuContext

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
            self, self.interaction  # type: ignore[arg-type]
        )

    @property
    def responses(self) -> List[Response]:
        return self._responses
    
    @property
    def last_response(self) -> Response | None:  # type: ignore[override]
        return self._responses[-1] if self._responses else None
    
    @property
    def first_response(self) -> Response | None:
        return self._responses[0] if self._responses else None
    
    async def respond(  # type: ignore[override]
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
    
    async def delete_initial_response(self):
        await self.response_state.delete_initial_response()
    
    async def delete_webhook_message(self, message: SnowflakeishOr[hikari.Message], after: int | None = None) -> None:
        await self.response_state.delete_webhook_message(message)
        
    async def edit_last_response(
        self, 
        embeds: List[hikari.Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> hikari.Message:
        return await self.response_state.edit_last_response()

    async def defer(self, update: bool = False, background: bool = False):
        await self.response_state.defer(update=update)
        
    @classmethod
    def from_event(cls, interaction: Interaction) -> "BaseInteractionContext":
        return cls(interaction.app, interaction)

    @classmethod
    def from_ctx(cls, ctx: Context) -> "BaseInteractionContext":
        raise NotImplementedError
    
    def set(self, **kwargs: Any):
        return

class CommandInteractionContext(BaseInteractionContext, AuthorMixin, GuildsAndChannelsMixin):  # type: ignore[union-attr]
    def __init__(self, app: Inu, interaction: hikari.CommandInteraction) -> None:
        super().__init__(app, interaction)
        


class InteractionContext(BaseInteractionContext, AuthorMixin, GuildsAndChannelsMixin):  # type: ignore[union-attr]
    def __init__(self, app: Inu, interaction: hikari.ComponentInteraction) -> None:
        super().__init__(app, interaction)
        
    @property
    def custom_id(self) -> str:
        return self.interaction.custom_id
    
    @property
    def interaction(self) -> ComponentInteraction:
        return self._interaction  # type: ignore
    
        