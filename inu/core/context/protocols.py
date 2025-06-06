from typing import *
from abc import ABC, abstractmethod
from datetime import timedelta


import hikari
from hikari import (
    Message, Resourceish, Snowflake, SnowflakeishOr, TextInputStyle, 
    UndefinedOr, UNDEFINED, Embed, UndefinedNoneOr
)
from hikari.impl import MessageActionRowBuilder
from lightbulb.context import Context

from .mixins import GuildsAndChannelsMixin, AuthorMixin, CustomIDMixin
from ..bot import Inu

if TYPE_CHECKING:
    from .response_state import BaseResponseState
    from .response_proxy import ResponseProxy

T = TypeVar("T")
Interaction = Union[hikari.ModalInteraction | hikari.CommandInteraction | hikari.ComponentInteraction]
T_STR_LIST = TypeVar("T_STR_LIST", list[str], str)


class InuContext(ABC):
    update: bool

    @classmethod
    @abstractmethod
    def from_context(cls, ctx: Context) -> T:
        ...

    @classmethod
    @abstractmethod
    def from_event(cls, interaction: Interaction) -> T:
        ...
    
    @property
    @abstractmethod
    def original_message(self) -> Optional[hikari.Message]:
        ...

    @property
    @abstractmethod
    def custom_id(self) -> str:
        """the custom_id of the current interaction"""

    @property
    @abstractmethod
    def bot(self) -> Inu:
        ...

    @property
    @abstractmethod
    def user(self) -> hikari.User:
        ...

    @property
    @abstractmethod
    def author(self) -> hikari.User:
        ...
        
    @property
    @abstractmethod
    def member(self) -> hikari.Member | None:
        ...
    
    @property
    @abstractmethod
    def author_id(self) -> Snowflake:
        ...

    @property
    @abstractmethod
    def guild(self) -> hikari.Guild | None:
        ...
        
    @property
    @abstractmethod
    def guild_id(self) -> Snowflake | None:
        ...
        
    @property
    @abstractmethod
    def channel_id(self) -> Snowflake:
        ...
    
    @abstractmethod
    def get_channel(self) -> hikari.GuildChannel | None:
        ...

    @abstractmethod
    async def execute(self, *args, delete_after: timedelta | int | None = None, **kwargs) -> Message:
        ...

    @abstractmethod
    async def respond(
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
        ) -> "ResponseProxy":
        """Respond to an interaction or command with a message.

        Parameters
        ----------
        content : UndefinedOr[str], optional
            The text content of the message
        embed : UndefinedNoneOr[Embed], optional
            A single embed to send
        embeds : UndefinedOr[List[Embed]], optional
            List of embeds to send
        delete_after : timedelta | None, optional
            If set, delete the message after this duration
        ephemeral : bool, default False
            Whether the message should be ephemeral (only visible to command user)
        component : UndefinedNoneOr[MessageActionRowBuilder], optional
            A single component action row to add
        components : UndefinedOr[List[MessageActionRowBuilder]], optional
            List of component action rows to add
        flags : hikari.MessageFlag, default NONE
            Message flags to apply
        update : bool, default False
            Whether to update the original message instead of sending new one

        Returns
        -------
        ResponseProxy
            Proxy object for the sent message response

        Notes
        -----
        - Only one of `embed`/`embeds` and `component`/`components` can be used
        - Ephemeral messages cannot be deleted with delete_after
        
        Examples
        --------
        Simple text response:
        >>> await ctx.respond("Hello!")
        
        Ephemeral embed:
        >>> embed = Embed(title="Secret")
        >>> await ctx.respond(embed=embed, ephemeral=True)
        """
        ...
    @property
    @abstractmethod
    def id(self) -> int:
        """used to Compare `InuContext` classes"""
        ...

    @property
    def interaction(self) -> Interaction:
        ...

    @abstractmethod
    def is_responded(self) -> bool:
        "Whether or not the interaction has been responded to. Checks is the response state is not InitialResponseState"
    
    @abstractmethod
    async def defer(self, update: bool = False, background: bool = True):
        """
        Acknowledges the interaction if not rest is used.
        acknowledge with DEFFERED_MESSAGE_UPDATE if self._update is True,
        otherwise acknowledge with DEFFERED_MESSAGE_CREATE

        Args:
        -----
        update : bool = False
            wether or not to update the current interaction message
        background : `bool` = True
            wether or not to defer it as background task

        
        Note:
        -----
        A task will be started, so it runs in background and returns instantly
        """
        ...
    
    @abstractmethod
    async def auto_defer(self) -> None:
        """
        Waits the about 3 seconds - REST_SENDING_MARGIN and acks then the
        interaction.

        Note:
        -----
        this runs as task in the background
        """
        ...

    @property
    def is_hashable(self) -> bool:
        """wether or not __hash__ will result in an error"""
        return self.id is not None
    
    @property
    def last_response(self) -> Message:
        """the last response message"""
        ...
    
    
    @abstractmethod
    async def delete_initial_response(self) -> None:
        ...
        
    @abstractmethod
    async def delete_webhook_message(self, message: int | hikari.Message, after: int | None = None):
        """
        delete a webhook message

        Args:
        ----
        message : int
            the message to delete. Needs to be created by this interaction
        after : int
            wait <after> seconds, until deleting
        """
    @abstractmethod
    def enforce_update(self, value: bool):
        """Whether to enforce updating the message with respond()"""
        ...
        
    @abstractmethod
    async def ask(
            self, 
            title: str, 
            button_labels: List[str] = ["Yes", "No"], 
            ephemeral: bool = True, 
            timeout: int = 120,
            delete_after_timeout: bool = False,
            allowed_users: List[hikari.SnowflakeishOr[hikari.User]] | None = None
    ) -> Tuple[str, "InuContext"]:
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
        """
        ask a question with buttons

        Args:
        -----
        title : str
            the title of the message
        timeout : int
            the timeout in seconds
        question_s : `Union[List[str], str]`
            The question*s to ask the user
        interaction : `ComponentInteraction`
            The interaction to use for initial response
        placeholder : `str` | `None`
            The placeholder of the input
        max_length : `int` | `None`
            The max length of the input
        min_length : `int` | `None`
            The min length of the input


        Returns:
        --------
        Tuple[str, "InteractionContext"]
            the selected label and the new context
        """
        ...

    async def cache_last_response(self) -> None:
        """
        fetches the message of the last response if not already done
        """
        ...
    
    async def message(self) -> hikari.Message:
        """
        fetches or returns the initial response message
        """
        ...

    @property
    @abstractmethod
    def message_id(self) -> hikari.Snowflake | None:
        """the ID of the initial response message if there is one"""
        ...

    async def edit_last_response(
        self,
        embeds: List[hikari.Embed] | None = None,
        content: str | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> Message:
        """edits the last response"""
        ...

    @property
    @abstractmethod
    def response_state(self) -> "BaseResponseState":
        ...

    @property
    @abstractmethod
    def needs_response(self) -> bool:
        """Whether or not the interaction needs a response. Need is definded, that otherwise an error would be raised"""
        ...

    @property
    def display_name(self) -> str:
        """returns the display name, if user is a member, otherwise the username"""
        ...
    
class InuContextProtocol(Protocol[T]):
    def from_context(cls: Context, ctx: Context) -> T:
        ...
    
    def from_event(cls: Context, event: hikari.Event) -> T:
        ...

    @property
    def initial_response(self) -> hikari.Message:
        ...

    @property
    def interaction(self) -> Interaction:
        ...
    
    async def defer(self, background: bool = True):
        """
        Acknowledges the interaction if not rest is used.
        acknowledge with DEFFERED_MESSAGE_UPDATE if self._update is True,
        otherwise acknowledge with DEFFERED_MESSAGE_CREATE

        Args:
        -----
        background : `bool` = True
            wether or not to defer it as background task

        
        Note:
        -----
        A task will be started, so it runs in background and returns instantly
        """
        ...
    
    async def auto_defer(self) -> None:
        """
        Waits the about 3 seconds - REST_SENDING_MARGIN and acks then the
        interaction.

        Note:
        -----
        this runs as task in the background
        """
        ...
    
    @property
    def bot(self) -> hikari.GatewayBot:
        ...

    @property
    def user(self) -> hikari.User:
        ...

    async def respond(self, *args, **kwargs):
        """
        Create a response for this context. The first time this method is called, the initial
        interaction response will be created by calling
        :obj:`~hikari.interactions.command_interactions.CommandInteraction.create_initial_response` with the response
        type set to :obj:`~hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE` if not otherwise
        specified.

        Subsequent calls will instead create followup responses to the interaction by calling
        :obj:`~hikari.interactions.command_interactions.CommandInteraction.execute`.

        Args:
            update : bool | SnowflakeishOr[hikari.Message] = False
                wether or not to update the current interaction message. Also message object is possible
            *args (Any): Positional arguments passed to ``CommandInteraction.create_initial_response`` or
                ``CommandInteraction.execute``.
            delete_after (Union[:obj:`int`, :obj:`float`, ``None``]): The number of seconds to wait before deleting this response.
            **kwargs: Keyword arguments passed to ``CommandInteraction.create_initial_response`` or
                ``CommandInteraction.execute``.

        Returns:
            :obj:`~ResponseProxy`: Proxy wrapping the response of the ``respond`` call.

        .. versionadded:: 2.2.0
            ``delete_after`` kwarg.
        """
        ...

    @property
    def id(self):
        """used to Compare `InuContext` classes"""
        ...
    

    async def auto_defer(self) -> None:
        """
        Waits the about 3 seconds - REST_SENDING_MARGIN and acks then the
        interaction.

        Note:
        -----
        this runs as task in the background
        """
        ...

    @property
    def is_hashable(self) -> bool:
        """wether or not __hash__ will result in an error"""
        return self.id is not None
    
    
    async def delete_inital_response(self) -> None:
        """deletes the initial response"""
        ...
        
