from typing import *

import hikari
import lightbulb
from lightbulb.context import *

from .protocols import InuContext, InuContextProtocol
from .interactions import InteractionContext, CommandInteractionContext, MessageInteractionContext, ModalInteractionContext
from .rest import RESTContext

ContextEvent = Union[hikari.MessageCreateEvent, hikari.InteractionCreateEvent]

def get_context(
    event: ContextEvent, 
    **kwargs,
) -> InuContext:
    """
    Args:
    -----
    event : `ContextEvent`
        the event to create the `InuContext` out of
    **kwargs : Any
        these kwargs will be passed into InuContext.set() to specify a class
        options: Dict[str, Any]
            the options of the command
        deferred: bool
            whether the context is deferred
        responded: bool
            whether the context got responded
    
    Returns:
    --------
    InuContext :
        - RESTContext when event is MessageCreateEvent
        - InteractionContext when event is InteractionCreateEvent

    """

    ctx_cls, custom_attrs = builder(event, **kwargs)
    ctx = ctx_cls.from_event(event=event)
    ctx.set(**custom_attrs)
    return ctx

def from_context():
    ...

def builder(event: ContextEvent, **kwargs) -> Tuple[Type[InuContext], Dict[str, Any]]:
    """
    returns the coresponding class to an event
    """
    if isinstance(event, hikari.MessageCreateEvent):
        return RESTContext, kwargs
    elif isinstance(event, hikari.MessageUpdateEvent):
        return RESTContext, kwargs
    if isinstance(event, hikari.InteractionCreateEvent):
        interaction = event.interaction
        if isinstance(interaction, hikari.ComponentInteraction):
            return InteractionContext, kwargs
        elif isinstance(interaction, hikari.ModalInteraction):
            return ModalInteractionContext, kwargs
        elif isinstance(interaction, hikari.CommandInteraction):
            return CommandInteractionContext, kwargs  # lightbulb acknowledges them automatically
        else:
            raise TypeError(
                f"Can't create `InuContext` out of an `InteractionCreateEvent` with `{type(interaction)}` as interaction"
            )
    else:
        raise TypeError(f"Can't create `InuContext` out of event with type `{type(event)}`")
    