from typing import *

import hikari
import lightbulb
from lightbulb.context import *

from .protocols import InuContext, InuContextProtocol
from .interactions import InteractionContext
from .rest import RESTContext

ContextEvent = Union[hikari.MessageCreateEvent, hikari.InteractionCreateEvent]

def get_context(event: ContextEvent) -> InuContextProtocol:
    """
    Args:
    -----
    event : `ContextEvent`
        the event to create the `InuContext` out of

    
    Returns:
    --------
    InuContextProtocol :
        - RESTContext when event is MessageCreateEvent
        - InteractionContext when event is InteractionCreateEvent
    """
    ctx_cls = builder(event)
    return ctx_cls.from_event(event=event)

def builder(event: ContextEvent) -> InuContext:
    if isinstance(event, hikari.MessageCreateEvent):
        return RESTContext
    if isinstance(event, hikari.InteractionCreateEvent):
        return InteractionContext
    else:
        raise TypeError(f"Can't create `InuContext` out of event with type `{type(event)}`")
    