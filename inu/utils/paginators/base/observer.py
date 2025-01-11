from operator import is_
from typing import *
from abc import ABCMeta, abstractmethod
import asyncio

import hikari
from hikari.impl import MessageActionRowBuilder
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
from utils import add_row_when_filled, is_row_filled

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
    def subscribe(self, listener: TListener, event: Type[TEventOrInteraction]):
        pass
    
    @abstractmethod
    def unsubscribe(self, listener: TListener, event: Type[TEventOrInteraction]):
        pass

    @abstractmethod
    async def notify(self, event: TEventOrInteraction):
        pass


class InteractionObserver(BaseObserver["InteractionListener", InteractionCreateEvent | ComponentInteraction]):
    """An Observer which receives hikari.PartialInteraction and notifies its listeners"""
    def __init__(self, pag):
        self._pag = pag
        self._listeners: Dict[Type[Any], List["InteractionListener | ButtonListener"]] = {}

    @property
    def listeners(self):
        return self._listeners

    def subscribe(self, listener: "InteractionListener | ButtonListener", event: Type[InteractionCreateEvent | ComponentInteraction]):
        log.debug(f"subscribed interaction listener to {event}")
        if not event in self._listeners.keys():
            self._listeners[event] = []
        self._listeners[event].append(listener)
    
    def unsubscribe(self, listener: "InteractionListener | ButtonListener", event: Type[InteractionCreateEvent | ComponentInteraction]):
        if event not in self._listeners.keys():
            return
        self._listeners[event].remove(listener)

    async def notify(self, event: InteractionCreateEvent | ComponentInteraction):
        if isinstance(event, ComponentInteraction):
            raise RuntimeError("notify should not be called with ComponentInteraction")
        log.debug(f"notify with {type(event)}; keys: {self._listeners.keys()}")
        if type(event) not in self._listeners.keys() and type(event.interaction) not in self._listeners.keys():
            return
        for type_, listeners in self._listeners.items():
            if not (type_ == type(event) or type_ == type(event.interaction)):
                continue
            for listener in listeners:
                # dispatch event to listeners
                if isinstance(listener, ButtonListener) and isinstance(event.interaction, ComponentInteraction):
                    # dispatch to @button
                    asyncio.create_task(listener.on_event(event.interaction))
                elif isinstance(listener, InteractionListener) and isinstance(event.interaction, PartialInteraction):
                    # dispatch to @listener
                    asyncio.create_task(listener.on_event(event.interaction))


class EventListener(BaseListener):
    """A Listener used to trigger hikari events"""
    def __init__(self, callback: Callable[["Paginator", Event], Any], event: Type[Event]):
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
    def __init__(self, callback: Callable[["Paginator", PartialInteraction], Any], event: Type[Event]):
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
        row: Optional[int] = None,
        startswith: Optional[str] = None,
    ):
        self.event = hikari.ComponentInteraction
        self._callback = callback
        self.name: Optional[str] = None
        self.paginator: Paginator
        self._label = label
        self._emoji: Optional[str] = emoji
        self._button_style: ButtonStyle = style
        self._custom_id_base = custom_id_base.replace(" ", "_")
        self._check: Callable[[ComponentInteraction], bool] = lambda i: i.custom_id.startswith(self._custom_id_base) 
        self._desired_row = row
        

    def use_check_startswith(self, startswith: str) -> "ButtonListener":
        self._check = lambda x: x.custom_id.startswith(startswith)
        return self
    
    def interactive_button_builder(self) -> InteractiveButtonBuilder: 
        return InteractiveButtonBuilder(
            style=self._button_style,
            custom_id=self._custom_id_base,
            emoji=self._emoji or UNDEFINED,
            label=self._label,
        )

    def add_to_row(
        self,
        rows: List[MessageActionRowBuilder]
    ):  
        while self._desired_row and len(rows) < self._desired_row:
            # add empty rows, to put button in desired row
            rows = add_row_when_filled(rows)

        for i, r in enumerate(rows):
            if (not self._desired_row or i == self._desired_row) and not is_row_filled(r):
                # add to desired row or next possible row
                r.add_component(self.interactive_button_builder())
                return
            
        if not rows or is_row_filled(rows[-1]):
            rows.append(MessageActionRowBuilder())
        rows[-1].add_component(self.interactive_button_builder())
    
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
    custom_id_base: Optional[str] = None,
    style: ButtonStyle = ButtonStyle.SECONDARY,
    emoji: Optional[str] = None,
    row: Optional[int] = None,
) -> Callable[[Callable], ButtonListener]:
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
    row (Optional[int]) default=None: the row of the button, defaults to the first possible row
    """
    if not custom_id_base:
        custom_id_base = label.lower()
    def decorator(func: Callable):
        observer = ButtonListener(
            callback=func,
            label=label,
            custom_id_base=custom_id_base,
            style=style,
            emoji=emoji,
            row=row,
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
        self._listeners: Dict[Type[Event], List[EventListener]] = {}

    @property
    def listeners(self):
        return self._listeners

    def subscribe(self, listener: EventListener, event: Type[Event]):
        log.debug(f"EventListener | subscribed listener to {event}")
        if event not in self._listeners.keys():
            self._listeners[event] = []
        self._listeners[event].append(listener)
    
    def unsubscribe(self, listener: EventListener, event: Type[Event]):
        if event not in self._listeners.keys():
            return
        self._listeners[event].remove(listener)

    async def notify(self, event: Event):
        log.debug(f"notify with {type(event)}; keys: {self._listeners.keys()}")
        if type(event) not in self._listeners.keys():
            return
        for listener in self._listeners[type(event)]:
            log.debug(f"observer pag: {self._pag.count} | notify listener with id {listener.paginator.count} | {listener.paginator._message.id if listener.paginator._message else None} | {listener.paginator}")
            asyncio.create_task(listener.on_event(event)) 

def listener(event: Any) -> Callable[[Callable], EventListener]:
    """A decorator to add listeners to a paginator"""
    def decorator(func: Callable):
        log.debug("listener registered")
        return EventListener(callback=func, event=event)
    return decorator