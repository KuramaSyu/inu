import asyncio
from types import prepare_class
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
    BaseResponseState, InitialResponseState, TInteraction,
    GuildsAndChannelsMixin, AuthorMixin, CustomIDMixin,
    MessageMixin, T_STR_LIST
)
from .base import InuContextBase, InuContext

if TYPE_CHECKING:
    from .base import InuContextBase, InuContext

log = getLogger(__name__)





class BaseInteractionContext(InuContextBase):  # type: ignore[union-attr]
    
    def __init__(self, app: Inu, interaction: TInteraction) -> None:
        self._interaction = interaction
        self.update: bool = False
        self._response_lock: asyncio.Lock = asyncio.Lock()
        self._app = app
        super().__init__()
    
    @property
    def original_message(self) -> hikari.Message:
        return super().original_message
    @property
    def app(self) -> Inu:
        return self._app
    
    @property
    def bot(self) -> Inu:
        return self._app
    
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
        content: str | None = None,
        embed: Embed | None = None,
        embeds: List[hikari.Embed] | None = None,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: List[MessageActionRowBuilder] | None = None,   
        flags: hikari.MessageFlag = hikari.MessageFlag.NONE
    ):
        embeds = embeds or [embed] if embed else []

        await self.response_state.respond(
            embeds=embeds,
            content=content,
            delete_after=delete_after,
            ephemeral=ephemeral,
            components=components,
            flags=flags
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
        return await self.response_state.edit_last_response()

    async def defer(self, update: bool = False, background: bool = False):
        await self.response_state.defer(update=update)
        
    @classmethod
    def from_event(cls, interaction: TInteraction) -> "BaseInteractionContext":
        if isinstance(interaction, hikari.InteractionCreateEvent):
            interaction = interaction.interaction  # type: ignore
        
        return cls(interaction.app, interaction)

    @classmethod
    def from_context(cls, ctx: Context) -> "BaseInteractionContext":
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
    ) -> Tuple[str, "InuContext"] | None:
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
        self._responses.append(proxy)
        selected_label, event, interaction = await self.app.wait_for_interaction(
            custom_ids=[f"{prefix}{l}" for l in button_labels],
            user_ids=allowed_users or self.author.id,
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
            title: str, 
            question_s: T_STR_LIST,
            input_style_s: Union[TextInputStyle, List[Union[TextInputStyle, None]]] = TextInputStyle.PARAGRAPH,
            placeholder_s: Optional[Union[str, List[Union[str, None]]]] = None,
            max_length_s: Optional[Union[int, List[Union[int, None]]]] = None,
            min_length_s: Optional[Union[int, List[Union[int, None]]]] = None,
            pre_value_s: Optional[Union[str, List[Union[str, None]]]] = None,
            is_required_s: Optional[Union[bool, List[Union[bool, None]]]] = None,
            timeout: int = 120
    ) -> Tuple[T_STR_LIST, "InteractionContext"] | Tuple[None, None]:
        try:
            answer_s, interaction, event = await self.app.shortcuts.ask_with_modal(
                modal_title=title,
                question_s=question_s,
                input_style_s=input_style_s,
                placeholder_s=placeholder_s,
                max_length_s=max_length_s,
                min_length_s=min_length_s,
                pre_value_s=pre_value_s,
                is_required_s=is_required_s,
                timeout=timeout,
                interaction=self.interaction
            )
            new_ctx = ComponentContext.from_event(event)
            return answer_s, new_ctx
        except asyncio.TimeoutError:
            return None, None



class CommandContext(BaseInteractionContext, AuthorMixin, GuildsAndChannelsMixin, MessageMixin):  # type: ignore[union-attr]
    def __init__(self, app: Inu, interaction: hikari.CommandInteraction) -> None:
        super().__init__(app, interaction)
    
    @property
    def interaction(self) -> CommandInteraction:
        return self._interaction
        
    async def message(self) -> hikari.Message:
        return await self.interaction.fetch_initial_response()

    @property
    def custom_id(self) -> None:
        return None


class ComponentContext(BaseInteractionContext, AuthorMixin, GuildsAndChannelsMixin, MessageMixin):  # type: ignore[union-attr]
    def __init__(self, app: Inu, interaction: hikari.ComponentInteraction) -> None:
        super().__init__(app, interaction)
        
    @property
    def custom_id(self) -> str:
        return self.interaction.custom_id
    
    @property
    def interaction(self) -> ComponentInteraction:
        return self._interaction  # type: ignore

    async def message(self) -> hikari.Message:
        return await self.interaction.fetch_initial_response()
        