from typing import Protocol, Union, runtime_checkable
import hikari
from hikari import Snowflake

# Define a protocol that requires the methods
@runtime_checkable
class InteractionContextProtocol(Protocol):
    @property
    def interaction(self) -> Union[
        hikari.CommandInteraction, 
        hikari.ComponentInteraction, 
        hikari.ModalInteraction
    ]: ...

    @property
    def app(self) -> 'Inu': ...

# Modify your existing mixins to use this protocol
class AuthorMixin:
    @property
    def author_id(self) -> Snowflake:
        assert isinstance(self, InteractionContextProtocol)
        return self.interaction.user.id

    @property
    def author(self) -> hikari.User:
        assert isinstance(self, InteractionContextProtocol)
        return self.interaction.user

    @property
    def user(self) -> hikari.User:
        assert isinstance(self, InteractionContextProtocol)
        return self.interaction.user

    @property
    def member(self) -> hikari.Member | None:
        assert isinstance(self, InteractionContextProtocol)
        if guild_id := getattr(self.interaction, 'guild_id', None):
            return self.app.cache.get_member(guild_id, self.author_id)
        return None

class GuildsAndChannelsMixin:
    @property
    def channel_id(self) -> Snowflake:
        assert isinstance(self, InteractionContextProtocol)
        return self.interaction.channel_id

    @property
    def guild_id(self) -> Snowflake | None:
        assert isinstance(self, InteractionContextProtocol)
        return getattr(self.interaction, 'guild_id', None)

    def get_channel(self) -> hikari.GuildChannel | None:
        assert isinstance(self, InteractionContextProtocol)
        return self.app.cache.get_guild_channel(self.channel_id)

    def get_guild(self) -> hikari.Guild | None:
        assert isinstance(self, InteractionContextProtocol)
        if guild_id := self.guild_id:
            return self.app.cache.get_guild(guild_id)
        return None

class MessageMixin:
    _initial_response_message: hikari.Message | None = None

    async def message(self) -> hikari.Message:
        assert isinstance(self, InteractionContextProtocol)
        if (msg := self._initial_response_message):
            return msg
        msg = await self.interaction.fetch_initial_response()
        self._initial_response_message = msg
        return msg

    @property
    def message_id(self) -> Snowflake | None:
        assert isinstance(self, InteractionContextProtocol)
        try:
            return self.interaction.message.id
        except Exception:
            if self._initial_response_message:
                return self._initial_response_message.id
            return None

    @property
    def initial_response(self) -> hikari.Message | None:
        return self._initial_response_message

class CustomIDMixin:
    @property
    def custom_id(self) -> str:
        assert isinstance(self, InteractionContextProtocol)
        return self.interaction.custom_id