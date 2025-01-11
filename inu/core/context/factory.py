from typing import *

import hikari
import lightbulb
from lightbulb.context import *

from .protocols import InuContext, InuContextProtocol
from .interactions import CommandContext, ComponentContext
from .rest import RestContext

ContextEvent = Union[hikari.MessageCreateEvent, hikari.InteractionCreateEvent, hikari.MessageUpdateEvent]
Interaction = Union[hikari.ModalInteraction | hikari.CommandInteraction | hikari.MessageInteraction | hikari.ComponentInteraction]

def get_context(
    event: ContextEvent | Interaction, 
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
    if isinstance(event, ContextEvent):
        if isinstance(event, (hikari.MessageCreateEvent, hikari.MessageUpdateEvent)):
            ctx_cls = cast(RestContext, ctx_cls)
            ctx = ctx_cls.from_event(event)
        else:
            ctx = ctx_cls.from_event(interaction=event.interaction)  # type: ignore
    else:
         ctx = ctx_cls.from_event(interaction=event)
    ctx.set(**custom_attrs)
    return ctx  # type: ignore

def from_context():
    ...

def builder(event: ContextEvent | Interaction, **kwargs) -> Tuple[Type[InuContext], Dict[str, Any]]:
    """
    returns the coresponding class to an event
    """
    if isinstance(event, hikari.MessageCreateEvent):
        return RestContext, kwargs  # type: ignore
    elif isinstance(event, hikari.MessageUpdateEvent):
        raise NotImplementedError("MessageUpdateEvent is not supported yet")
    if isinstance(event, hikari.InteractionCreateEvent) or isinstance(event, hikari.PartialInteraction):
        if isinstance(event, hikari.PartialInteraction):
            interaction = event
        else:
            interaction = event.interaction
        if isinstance(interaction, hikari.ComponentInteraction):
            return ComponentContext, kwargs  # type: ignore
        elif isinstance(interaction, hikari.ModalInteraction):
            raise NotImplementedError("ModalInteraction is not supported yet")
        elif isinstance(interaction, hikari.CommandInteraction):
            return CommandContext, kwargs  #type: ignore # lightbulb acknowledges them automatically
        else:
            raise TypeError(
                f"Can't create `InuContext` out of an `InteractionCreateEvent` with `{type(interaction)}` as interaction"
            )
    else:
        raise TypeError(f"Can't create `InuContext` out of event with type `{type(event)}`")
    