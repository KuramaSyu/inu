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
from . import InuContextProtocol, UniqueContextInstance, Response, BaseResponseState, InitialResponseState

if TYPE_CHECKING:
    from .base import InuContextBase, InuContext

log = getLogger(__name__)
Interaction = Union[hikari.ModalInteraction | hikari.CommandInteraction | hikari.MessageInteraction | ComponentInteraction]

class AppAware(Protocol):
    @property
    @abstractmethod
    def app(self) -> Inu:
        ...

class GuildChannelInteractionProtocol(Protocol):
    @property
    @abstractmethod
    def interaction(self) -> hikari.CommandInteraction | hikari.ComponentInteraction:
        ...

@attrs.define(kw_only=True)
class GuildsAndChannelsMixin(ABC, AppAware, GuildChannelInteractionProtocol):
    """
    A mixin for channel and guild properties.
    """

    @property
    def channel_id(self) -> Snowflake:
        """Channel ID where interaction was triggered"""
        return self.interaction.channel_id

    @property
    def guild_id(self) -> Snowflake | None:
        """Guild ID where interaction was triggered"""
        return self.interaction.guild_id

    
    def get_channel(self) -> hikari.GuildChannel | None:
        return self.app.cache.get_guild_channel(self.channel_id)

    def get_guild(self) -> hikari.Guild | None:
        if self.guild_id is None:
            return None
        return self.app.cache.get_guild(self.guild_id)


@attrs.define(kw_only=True)
class AuthorMixin(ABC):
    """
    A mixin for author properties.
    """

    @property
    @abstractmethod
    def interaction(self) -> Union[ModalInteraction, CommandInteraction, ComponentInteraction]:
        pass

    @property
    @abstractmethod
    def app(self) -> Inu:
        pass

    @property
    def author_id(self) -> Snowflake:
        """Author ID of the interaction"""
        return self.interaction.user.id

    @property
    def author(self) -> hikari.User:
        """Author of the interaction"""
        return self.interaction.user


@attrs.define(kw_only=True)
class CustomIDMixin(ABC):
    """
    A mixin for author properties.
    """
    @property
    @abstractmethod
    def interaction(self) -> hikari.ComponentInteraction | hikari.ModalInteraction:
        ...

    @property
    def custom_id(self) -> str:
        """Custom ID of the interaction"""
        return self.interaction.custom_id


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
        resp_id = await self.responses[0].respond(
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
        
    
    
        