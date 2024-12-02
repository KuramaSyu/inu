from typing import *
from abc import abstractmethod

import hikari
from hikari import Snowflake
from ..bot import Inu
#from . import InuContextProtocol, UniqueContextInstance, Response, BaseResponseState, InitialResponseState

Interaction = Union[
    hikari.ModalInteraction | hikari.CommandInteraction 
    | hikari.MessageInteraction | hikari.ComponentInteraction
]

class HasApp(Protocol):
    @property
    @abstractmethod
    def app(self) -> Inu:
        ...

class HasInteraction(Protocol):
    @property
    @abstractmethod
    def interaction(self) -> Interaction:
        ... 

class HasChannelLikeInteraction(Protocol):
    @property
    @abstractmethod
    def interaction(self) -> hikari.CommandInteraction | hikari.ComponentInteraction:
        ...


class GuildsAndChannelsMixin(HasChannelLikeInteraction, HasApp):
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


class AuthorMixin(HasInteraction):
    """
    A mixin for author properties. auth
    """

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


class CustomIDMixin():
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