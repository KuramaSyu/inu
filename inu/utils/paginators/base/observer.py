from typing import *
from abc import ABCMeta, abstractmethod
import asyncio

import hikari
from hikari import (
    ComponentInteraction,
    ButtonStyle,
    UNDEFINED,
    InteractionCreateEvent,
    PartialInteraction,
    Event,
)
from hikari.impl import InteractiveButtonBuilder

from core import Inu, getLogger, InuContext, get_context


if TYPE_CHECKING:
    from .base import Paginator

log = getLogger(__name__)




TListener = TypeVar("TListener", bound="BaseListener")  # to accept BaseListener and its subclasses
TEventOrInteraction = TypeVar("TEventOrInteraction", bound=Union[Event, PartialInteraction])



class BaseListener(Generic[TEventOrInteraction], metaclass=ABCMeta):
    """A Base Listener. It will receive events from an Observer"""
    @property
    def callback(self):
        raise NotImplementedError

    @abstractmethod
    async def on_event(self, event: TEventOrInteraction):
        raise NotImplementedError



class BaseObserver(Generic[TListener, TEventOrInteraction], metaclass=ABCMeta):
    """A Base Observer. This will later notify all listeners on event"""
    @property
    def listeners(self):
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, listener: TListener, event: TEventOrInteraction):
        pass
    
    @abstractmethod
    def unsubscribe(self, listener: TListener, event: TEventOrInteraction):
        pass

    @abstractmethod
    async def notify(self, event: TEventOrInteraction):
        pass


class InteractionObserver(BaseObserver["InteractionListener", InteractionCreateEvent]):
    """An Observer which receives hikari.PartialInteraction and notifies its listeners"""
    def __init__(self, pag):
        self._pag = pag
        self._listeners: Dict[str, List[InteractionListener]] = {}

    @property
    def listeners(self):
        return self._listeners

    def subscribe(self, listener: "InteractionListener", event: InteractionCreateEvent):
        log.debug(f"subscribed interaction listener to {str(type(event))}")
        if str(type(event)) not in self._listeners.keys():
            self._listeners[str(event)] = []
        self._listeners[str(event)].append(listener)
    
    def unsubscribe(self, listener: "InteractionListener", event: InteractionCreateEvent):
        if str(type(event)) not in self._listeners.keys():
            return
        self._listeners[str(event)].remove(listener)

    async def notify(self, event: InteractionCreateEvent):
        if str(type(event)) not in self._listeners.keys():
            return
        for listener in self._listeners[str(type(event))]:
            asyncio.create_task(listener.on_event(event.interaction))


class EventListener(BaseListener):
    """A Listener used to trigger hikari events"""
    def __init__(self, callback: Callable[["Paginator", Event], Any], event: str):
        self._callback = callback
        self.event = event
        self.name: Optional[str] = None
        self.paginator: "Paginator"

    @property
    def callback(self) -> Callable:
        return self._callback

    async def on_event(self, event: Event):
        await self.callback(self.paginator, event)


class InteractionListener(BaseListener[PartialInteraction]):
    """A Listener used to trigger hikari interactions"""
    def __init__(self, callback: Callable[["Paginator", PartialInteraction], Any], event: str):
        self._callback = callback
        self.event = event
        self.name: Optional[str] = None
        self.paginator: Paginator

    @property
    def callback(self) -> Callable:
        return self._callback

    async def on_event(self, event: PartialInteraction):
        await self.callback(self.paginator, event)



class ButtonListener(BaseListener):
    """A Listener used to trigger hikari ComponentInteractions, given from the paginator"""
    def __init__(
        self, 
        callback: Callable[["Paginator", InuContext, ComponentInteraction], Any], 
        label: str,
        custom_id_base: str,
        style: ButtonStyle = ButtonStyle.SECONDARY,
        emoji: Optional[str] = None,
        startswith: Optional[str] = None,
    ):
        self.event = str(hikari.ComponentInteraction)
        self._callback = callback
        self.name: Optional[str] = None
        self.paginator: Paginator
        self._label = label
        self._emoji: Optional[str] = emoji
        self._button_style: ButtonStyle = style
        self._custom_id_base = custom_id_base
        self._check: Callable[[ComponentInteraction], bool] = lambda i: i.custom_id.startswith(self._custom_id_base) 
        

    def use_check_startswith(self, startswith: str) -> "ButtonListener":
        self._check = lambda x: x.custom_id.startswith(startswith)
        return self
    
    def button_args(
        self, 
        paginator: "Paginator", 
    ) -> InteractiveButtonBuilder: 
        return InteractiveButtonBuilder(
            style=self._button_style,
            custom_id=self._custom_id_base,
            emoji=self._emoji or UNDEFINED,
            label=self._label,
        )
    
    @property
    def callback(self) -> Callable[["Paginator", InuContext, ComponentInteraction], Any]:
        return self._callback

    async def on_event(self, event: ComponentInteraction):
        ctx = get_context(event)
        if not (isinstance(event, ComponentInteraction) and self._check(event)):
            return
        await self.callback(self.paginator, ctx, event)
        
# not x or not y
#
# == eq
#
# not (x and y)
#
# <> opposite
#
# x and y

def button(
    label: str,
    custom_id_base: str,
    style: ButtonStyle = ButtonStyle.SECONDARY,
    emoji: Optional[str] = None,
):
    """
    A decorator factory to create a Button and also add it to the listener of the paginator.
    
    Example:
    --------
    ```py
    @button(label="Next", custom_id_base="next", style=ButtonStyle.PRIMARY, emoji="▶")
    async def next_button(self: Paginator, ctx: InuContext, event: InteractionCreateEvent):
        ...
    ```
    
    Args:
    -----
    label (str): the label of the button
    custom_id_base (str): how the custom_id starts. This will also be used to create the component
    style (Buttonstyle) default=ButtonStyle.SECONDARY: the style of the button
    emoji (Optional[str]) default=None: the emoji of the button
    """
    
    def decorator(func: Callable):
        observer = ButtonListener(
            callback=func,
            label=label,
            custom_id_base=custom_id_base,
            style=style,
            emoji=emoji
        )
        return observer
        # set label
    return decorator

# TODO: option to set add_button to None, to manually build it

# a second decorator which consumes the output of the button decorator factory to specify a method 


class EventObserver(BaseObserver[EventListener, Event]):
    """An Observer which receives events from a Paginator and notifies its listeners about it"""
    def __init__(self, pag):
        self._pag = pag
        self._listeners: Dict[str, List[EventListener]] = {}

    @property
    def listeners(self):
        return self._listeners

    def subscribe(self, listener: EventListener, event: Event):
        if event not in self._listeners.keys():
            self._listeners[str(event)] = []
        self._listeners[str(event)].append(listener)
    
    def unsubscribe(self, listener: EventListener, event: Event):
        if event not in self._listeners.keys():
            return
        self._listeners[str(event)].remove(listener)

    async def notify(self, event: Event):
        if str(type(event)) not in self._listeners.keys():
            return
        for listener in self._listeners[str(type(event))]:
            log.debug(f"observer pag: {self._pag.count} | notify listener with id {listener.paginator.count} | {listener.paginator._message.id if listener.paginator._message else None} | {listener.paginator}")
            asyncio.create_task(listener.on_event(event)) 

def listener(event: Any):
    """A decorator to add listeners to a paginator"""
    def decorator(func: Callable):
        log.debug("listener registered")
        return EventListener(callback=func, event=str(event))
    return decorator