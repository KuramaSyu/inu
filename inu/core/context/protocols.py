from typing import *
from abc import ABC, abstractmethod

import hikari
from lightbulb.context import Context


T = TypeVar("T")


class InuContext(ABC):
    @abstractmethod
    def from_context(cls: Context, ctx: Context) -> T:
        ...

    @abstractmethod
    def from_event(cls: Context, event: hikari.Event) -> T:
        ...
    
    @property
    @abstractmethod
    def original_message(self) -> hikari.Message:
        ...

    @property
    @abstractmethod
    def bot(self) -> hikari.GatewayBot:
        ...

    @property
    @abstractmethod
    def user(self) -> hikari.User:
        ...

    @abstractmethod
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
            update : bool
                wether or not to update the current interaction message
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



class InuContextProtocol(Protocol[T]):
    def from_context(cls: Context, ctx: Context) -> T:
        ...
    
    def from_event(cls: Context, event: hikari.Event) -> T:
        ...

    @property
    def original_message(self) -> hikari.Message:
        ...
