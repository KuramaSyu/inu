from typing import *

import hikari
import lightbulb
from lightbulb.context import *

from .protocols import InuContext, InuContextProtocol
from .interactions import InteractionContext, CommandInteractionContext
from .rest import RESTContext

ContextEvent = Union[hikari.MessageCreateEvent, hikari.InteractionCreateEvent]

def get_context(
    event: ContextEvent, 
    **kwargs,
) -> InuContextProtocol:
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

    ctx_cls, custom_attrs = builder(event, **kwargs)
    ctx = ctx_cls.from_event(event=event)
    ctx.set(**custom_attrs)
    return ctx

def from_context():
    ...

def builder(event: ContextEvent, **kwargs) -> Tuple[Type[InuContext], Dict[str, Any]]:
    if isinstance(event, hikari.MessageCreateEvent):
        return RESTContext, {}
    if isinstance(event, hikari.InteractionCreateEvent):
        interaction = event.interaction
        if isinstance(interaction, hikari.ComponentInteraction):
            return InteractionContext, {}
        elif isinstance(interaction, hikari.CommandInteraction):
            # command interactions from lightbulb are either deferred or responded
            # when auto_defer is True, then it's responded
            if not kwargs.get("responded"):
                #kwargs["deferred"] = True
                pass
            return CommandInteractionContext, kwargs  # lightbulb acknowledges them automatically
        else:
            raise TypeError(
                f"Can't create `InuContext` out of an `InteractionCreateEvent` with `{type(interaction)}` as interaction"
            )
    else:
        raise TypeError(f"Can't create `InuContext` out of event with type `{type(event)}`")
    