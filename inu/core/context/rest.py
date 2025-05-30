"""Context based on REST responses"""
from operator import is_
from typing import * 
from datetime import timedelta, datetime

import asyncio
import hikari
from hikari import Message, MessageCreateEvent, MessageUpdateEvent, Snowflake, SnowflakeishOr, Embed, UndefinedNoneOr, UndefinedOr, UNDEFINED, Resourceish
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb import Context


from . import (
    InuContextProtocol, InuContext, InuContextBase, 
    UniqueContextInstance, ComponentContext, GuildsAndChannelsMixin, AuthorMixin,
    Response, ResponseProxy, 
)
from .response_state import RestResponseState

from .._logging import getLogger
from ..bot import Inu


log = getLogger(__file__)


class RestContext(InuContextBase, GuildsAndChannelsMixin, AuthorMixin):
 
    def __init__(self, app: Inu, message: Message) -> None:
        self._message = message
        self.update: bool = False
        self._response_lock: asyncio.Lock = asyncio.Lock()
        self._app = app
        self.update = False
        self._defered = False
        self._responded = False
        self._responses: List[Response] = []
        self._bot: Inu = Inu.instance
        self._response_state = RestResponseState(None, self, [], message)
    
    @property
    def needs_response(self) -> bool:
        """RestContext theorethically never needs a response"""
        return False

    @property
    def interaction(self) -> None:
        return None

    @property
    def message(self) -> Message:
        return self._message

    @property
    def original_message(self) -> hikari.Message:
        return self._message
    @property
    def app(self) -> Inu:
        return self._app
    
    @property
    def bot(self) -> Inu:
        return self._app
    
    @property
    def id(self) -> Snowflake:
        return self._message.id

    @property
    def responses(self) -> List[Response]:
        return self._responses
    
    @property
    def last_response(self) -> Optional[ResponseProxy]:  # type: ignore[override]
        return self.response_state.responses[-1] if self.response_state.responses else None
    
    @property
    def first_response(self) -> Optional[ResponseProxy]:
        return self.response_state.responses[0] if self.response_state.responses else None
    
    async def respond(  # type: ignore[override]
        self, 
        content: UndefinedOr[str] = UNDEFINED,
        embed: UndefinedNoneOr[Embed] = UNDEFINED,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        component: UndefinedNoneOr[MessageActionRowBuilder] = UNDEFINED,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,   
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE,
        update: SnowflakeishOr[Message] | bool = False,
        attachment: UndefinedNoneOr[Resourceish] = UNDEFINED,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,
    ) -> ResponseProxy:
        embeds = embeds or [embed] if embed else []
        components = components or ([component] if component else [])
        if not attachment in [UNDEFINED, None] and not attachments:
            attachments = [attachment]  # type: ignore
        log.debug(f"respond() with {type(self.response_state).__name__} and {update=}")
        return await self.response_state.respond(
            embeds=embeds,
            content=content,
            delete_after=delete_after,
            ephemeral=ephemeral,
            components=components,
            flags=flags,
            update=update,
            attachments=attachments
        )
    
    async def delete_initial_response(self):
        await self.response_state.delete_initial_response()
    
    async def delete_webhook_message(self, message: SnowflakeishOr[hikari.Message], after: int | None = None) -> None:
        await self.response_state.delete_webhook_message(message)
    
    async def execute(
        self,
        content: str,
        embeds: List[Embed] | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> hikari.Message:
        return await self.response_state.execute(
            content=content,
            embeds=embeds,
            components=components
        )
    async def edit_last_response(
        self, 
        embeds: List[hikari.Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> hikari.Message:
        return await self.response_state.edit_last_response(
            embeds=embeds,
            content=content,
            components=components
        )

    async def defer(self, update: bool = False, background: bool = False):
        await self.response_state.defer(update=update)
        
    @classmethod
    def from_event(cls, interaction: MessageCreateEvent | MessageUpdateEvent) -> "RestContext":
        return cls(interaction.app, interaction.message)  # type:ignore

    @classmethod
    def from_context(cls, ctx: Context) -> "RestContext":
        raise NotImplementedError
    
    def set(self, **kwargs: Any):
        return

    async def ask(
        self, 
        title: str, 
        button_labels: List[str] = ["Yes", "No"], 
        ephemeral: bool = True, 
        timeout: int = 120,
        delete_after_timeout: bool = False,
        allowed_users: List[hikari.SnowflakeishOr[hikari.User]] | None = None
    ) -> Tuple[str, "InuContext"] | Tuple[None, None]:
        """
        ask a question with buttons

        Args:
        -----
        title : str
            the title of the message
        button_labels : List[str]
            the labels of the buttons
        ephemeral : bool
            whether or not the message should be ephemeral
        timeout : int
            the timeout in seconds
        allowed_users : List[hikari.User]
            the users allowed to interact with the buttons

        Returns:
        --------
        Tuple[str, "InuContext"]
            the selected label and the new context
        """
        prefix = "ask_"
        components: List[MessageActionRowBuilder] = []
        for i, label in enumerate(button_labels):
            if i % 5 == 0:
                components.append(MessageActionRowBuilder())
            components[0].add_interactive_button(
                hikari.ButtonStyle.SECONDARY,
                f"{prefix}{label}",
                label=label
            )
        proxy = await self.respond(title, components=components, ephemeral=ephemeral)
        selected_label, event, interaction = await self.app.wait_for_interaction(
            custom_ids=[f"{prefix}{l}" for l in button_labels],
            user_ids=allowed_users or self.author.id,  # type:ignore
            message_id=(await proxy.message()).id,
            timeout=timeout
        )
        if not all([selected_label, event, interaction]):
            return None, None
        if delete_after_timeout:
            await proxy.delete()
        new_ctx = ComponentContext.from_event(event)
        return selected_label.replace(prefix, "", 1), new_ctx
    
    async def auto_defer(self) -> None:
        return await self.defer()

    async def ask_with_modal(
            self, 
            **kwargs
    ) -> Tuple[str | List[str], "RestContext"] | Tuple[None, None]:
        raise NotImplementedError(f"`ask_with_modal` does not work with {self.__class__.__name__}")

    @property
    def channel_id(self) -> Snowflake:
        return self._message.channel_id

    @property
    def guild_id(self) -> Snowflake | None:
        self._message.guild_id

    def get_channel(self) -> hikari.GuildChannel | None:
        return self.app.cache.get_guild_channel(self._message.channel_id)

    def get_guild(self) -> hikari.Guild | None:
        if guild_id := self.guild_id:
            return self.app.cache.get_guild(guild_id)
        return None

    @property
    def author_id(self) -> Snowflake:
        return self._message.author.id

    @property
    def author(self) -> hikari.User:
        return self._message.author

    @property
    def user(self) -> hikari.User:
        return self._message.author

    @property
    def member(self) -> hikari.Member | None:
        if guild_id := getattr(self.interaction, 'guild_id', None):
            return self.app.cache.get_member(guild_id, self.author_id)
        return None
    
    async def message(self) -> hikari.Message:
        return self._message
    
    @property
    def message_id(self) -> Snowflake:
        return self._message.id