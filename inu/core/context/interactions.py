import asyncio
from multiprocessing import get_context
from types import prepare_class
from typing import *
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import functools
import attrs
import hikari
from hikari import (
    UNDEFINED, CacheAware, CommandInteraction, ComponentInteraction, GuildChannel, InteractionCreateEvent, Message, ModalInteraction, PartialInteraction, RESTAware, Resourceish, ResponseType, 
    Snowflake, TextInputStyle, SnowflakeishOr, Embed, UndefinedOr, UndefinedNoneOr
)
from hikari import embeds
from hikari.impl import MessageActionRowBuilder

from .._logging import getLogger
import lightbulb
from lightbulb import Context, attachment
from hikari import CommandInteractionOption

from ..bot import Inu
from . import (
    InuContextProtocol, UniqueContextInstance, Response, 
    BaseResponseState, InitialResponseState, TInteraction,
    GuildsAndChannelsMixin, AuthorMixin, CustomIDMixin,
    MessageMixin, T_STR_LIST, ResponseProxy, DeferredCreateResponseState
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
    def needs_response(self) -> bool:
        return isinstance(self.response_state, (InitialResponseState, DeferredCreateResponseState))
    
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
        update = update or self.update
        
        # mappings from single item to list
        # TODO: this does not handle, if single item and list are both provided
        if not embed in [None, UNDEFINED] and embeds == UNDEFINED:
            embeds = [embed]  # type: ignore
        if not attachment in [None, UNDEFINED] and attachments is UNDEFINED:
            attachments = [attachment]  # type: ignore
        if not component in [None, UNDEFINED] and components is UNDEFINED:
            components = [component]  # type: ignore
            
        log.debug(f"respond() with {type(self.response_state).__name__} and {update = }")
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
        content: UndefinedOr[str] = UNDEFINED,
        embed: UndefinedNoneOr[Embed] = UNDEFINED,
        embeds: UndefinedOr[List[Embed]] = UNDEFINED,
        delete_after: timedelta | None = None,
        component: UndefinedNoneOr[MessageActionRowBuilder] = UNDEFINED,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,   
        attachment: UndefinedNoneOr[Resourceish] = UNDEFINED,
        attachments: UndefinedOr[List[Resourceish]] = UNDEFINED,
    ) -> hikari.Message:
        if not embed in [None, UNDEFINED] and embeds == UNDEFINED:
            embeds = [embed]  # type: ignore
        if not attachment in [None, UNDEFINED] and attachments is UNDEFINED:
            attachments = [attachment]  # type: ignore
        if not component in [None, UNDEFINED] and components is UNDEFINED:
            components = [component]  # type: ignore
            
        return await self.response_state.execute(
            content=content,
            embeds=embeds,
            components=components
        )
    async def edit_last_response(
        self,
        embeds: UndefinedOr[List[hikari.Embed]] = UNDEFINED,
        content: UndefinedOr[str] = UNDEFINED,
        components: UndefinedOr[List[MessageActionRowBuilder]] = UNDEFINED,
    ) -> hikari.Message:
        return await self.response_state.edit_last_response(
            embeds=embeds,
            content=content,
            components=components
        )

    async def defer(self, update: bool = False, background: bool = False):
        await self.response_state.defer(update=update)
        
    @classmethod
    def from_event(cls, interaction: TInteraction | InteractionCreateEvent) -> "BaseInteractionContext":
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
        None
            if the timeout is reached
        """
        prefix = "ask_"
        components: List[MessageActionRowBuilder] = []
        for i, label in enumerate(button_labels):
            if i % 5 == 0:
                components.append(MessageActionRowBuilder())
            components[-1].add_interactive_button(
                hikari.ButtonStyle.SECONDARY,
                f"{prefix}{label}",
                label=label
            )
        log.debug(f"components: {components}")
        proxy = await self.respond(title, components=components, ephemeral=ephemeral)
        selected_label, event, interaction = await self.app.wait_for_interaction(
            custom_ids=[f"{prefix}{l}" for l in button_labels],
            user_ids=allowed_users or self.author.id,  # type:ignore
            message_id=(await proxy.message()).id,
            timeout=timeout
        )
        if not all([selected_label, event, interaction]):
            return None
        if delete_after_timeout:
            await proxy.delete()
        assert event is not None
        new_ctx = ComponentContext.from_event(event)
        return selected_label.replace(prefix, "", 1), new_ctx  # type: ignore
    
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
    ) -> Tuple[T_STR_LIST, "InuContext"] | Tuple[None, None]:
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

    @property
    def original_message(self) -> Optional[hikari.Message]:
        return None

    @property
    def id(self) -> int:
        return self.interaction.id


class ComponentContext(BaseInteractionContext, AuthorMixin, GuildsAndChannelsMixin, MessageMixin):  # type: ignore[union-attr]
    def __init__(self, app: Inu, interaction: hikari.ComponentInteraction) -> None:
        super().__init__(app, interaction)
        
    @property
    def id(self) -> int:
        return self.interaction.id
    
    @property
    def custom_id(self) -> str:
        return self.interaction.custom_id
    
    @property
    def interaction(self) -> ComponentInteraction:
        return self._interaction  # type: ignore

    async def message(self) -> hikari.Message:
        return await self.interaction.fetch_initial_response()

    @property
    def original_message(self) -> hikari.Message:
        return self.interaction.message
