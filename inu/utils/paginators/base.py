import asyncio
from code import interact
from contextlib import suppress
from pprint import pformat
from typing import (
    Any,
    Callable,
    Optional,
    Sequence,
    TypeVar,
    Union,
    List,
    Final,
    Dict,
    Generic,
    Type,
)
import json
import traceback
import logging
from abc import abstractmethod, ABCMeta, ABC
from copy import deepcopy
import random
import time

import textwrap

import hikari
from hikari.embeds import Embed
from hikari.messages import Message
from hikari.impl import MessageActionRowBuilder, InteractiveButtonBuilder
from hikari import ButtonStyle, ComponentInteraction, GuildMessageCreateEvent, InteractionCreateEvent, MessageCreateEvent, NotFoundError, ResponseType
from hikari.events.base_events import Event
import lightbulb
from lightbulb.context import Context

from core import InteractionContext, RESTContext, InuContext, get_context, BotResponseError, getLogger

LOGLEVEL = logging.WARNING
log = logging.getLogger(__name__)
log.setLevel(LOGLEVEL)

__all__: Final[List[str]] = ["Paginator", "BaseListener", "BaseObserver", "EventListener", "EventObserver"]
_Sendable = Union[Embed, str]
T = TypeVar("T")

count = 0
REJECTION_MESSAGES = [
    "Doesn't really look like your menu, don't you think?",
    "_beep beeeeep_ 405 METHOD NOT ALLOWED - "
    "touching others property is prohibited. Only touching yours is allowed",
    "_beep beeeeep_ 403 VORBIDDEN - "
    "if it was your menu, you would have been able to click it",
    "_beep beeeeep_ 401 UNAUTHORIZED - "
    "imagine not even having enough permissions to click a button",
    "Never heard of [privacy](https://en.wikipedia.org/wiki/Privacy)?"
]
NUMBER_BUTTON_PREFIX = "pagination_page_"

class PaginatorReadyEvent(hikari.Event):
    def __init__(self, bot: lightbulb.BotApp):
        self.bot = bot

    @property
    def app(self):
        return self.bot

class PaginatorTimeoutEvent(hikari.Event):
    def __init__(self, bot: lightbulb.BotApp):
        self.bot = bot

    @property
    def app(self):
        return self.bot

class BaseListener(metaclass=ABCMeta):
    """A Base Listener. This will later notify all observers on event"""
    @property
    def observers(self):
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, observer: "EventObserver", event: Event):
        pass
    
    @abstractmethod
    def unsubscribe(self, observer: "EventObserver", event: Event):
        pass

    @abstractmethod
    async def notify(self, event: Event):
        pass


class BaseObserver(metaclass=ABCMeta):
    """A Base Observer. It will receive events from a Listener"""
    @property
    def callback(self):
        raise NotImplementedError

    @abstractmethod
    async def on_event(self, event):
        raise NotImplementedError





class EventObserver(BaseObserver):
    """An Observer used to trigger hikari events, given from the paginator"""
    def __init__(self, callback: Callable, event: str):
        self._callback = callback
        self.event = event
        self.name: Optional[str] = None
        self.paginator: Paginator

    @property
    def callback(self) -> Callable:
        return self._callback

    async def on_event(self, event: Event):
        await self.callback(self.paginator, event)



class EventListener(BaseListener):
    """A Listener which receives events from a Paginator and notifies its observers about it"""
    def __init__(self, pag):
        self._pag = pag
        self._observers: Dict[str, List[EventObserver]] = {}
    @property
    def observers(self):
        return self._observers

    def subscribe(self, observer: EventObserver, event: Event):
        if event not in self._observers.keys():
            self._observers[str(event)] = []
        self._observers[str(event)].append(observer)
    
    def unsubscribe(self, observer: EventObserver, event: Event):
        if event not in self._observers.keys():
            return
        self._observers[str(event)].remove(observer)

    async def notify(self, event: Event):
        if str(type(event)) not in self._observers.keys():
            return
        for observer in self._observers[str(type(event))]:
            log.debug(f"listener pag: {self._pag.count} | notify observer with id {observer.paginator.count} | {observer.paginator._message.id} | {observer.paginator}")
            asyncio.create_task(observer.on_event(event)) 

def listener(event: Any):
    """A decorator to add listeners to a paginator"""
    def decorator(func: Callable):
        log.debug("listener registered")
        return EventObserver(callback=func, event=str(event))
    return decorator


class JsonDict(dict):
    def as_json(self) -> str:
        """Convert the dictionary to a JSON string."""
        return json.dumps(self, indent=None, separators=(',', ':'))

    def as_dict(self) -> "JsonDict":
        """Return the dictionary itself."""
        return dict(self)


class CustomID():
    __slots__ = ["_type", "_custom_id", "_message_id", "_author_id", "_kwargs", "_page", "_position"]
    _type: str | None
    _custom_id: str
    _message_id: int | None
    _author_id: int | None
    _kwargs: Dict[str, str | int]

    def __init__(
        self,
        custom_id: str,
        type: str | None = None,
        message_id: int | None = None,
        author_id: int | None = None,
        page: int | None = None,
        **kwargs: Any,
    ):
        self._type = type
        self._custom_id = custom_id
        self._message_id = message_id
        self._author_id = author_id
        self._page = page
        self._kwargs = kwargs
        self._position: Optional[int] = None

    def _raise_none_error(self, var_name: str):
        raise TypeError(f"`{self.__class__.__name__}.{var_name}` is None. Make sure, to set it!")

    @property
    def type(self) -> str:
        if self._type is None:
            self._raise_none_error("_type")
        return self._type  #type: ignore

    @property
    def page(self) -> int:
        if self._page is None:
            self._raise_none_error("_page")
        return self._page  #type: ignore
    
    @property
    def custom_id(self) -> str:
        if self._custom_id is None:
            self._raise_none_error("_custom_id")
        return self._custom_id

    @property
    def message_id(self) -> int:
        if self._message_id is None:
            self._raise_none_error("_message_id")
        return self._message_id  #type: ignore
    
    @property
    def position(self) -> int:
        if self._position is None:
            self._raise_none_error("_position")
        return self._position
    
    @property
    def author_id(self) -> int:
        if self._author_id is None:
            self._raise_none_error("_author_id")
        return self._author_id  #type: ignore

    def is_same_user(self, interaction: hikari.ComponentInteraction):
        """wether or not the interaction user is the prvious paginator user"""
        return interaction.user.id == self.author_id
    
    def is_same_message(self, interaction: hikari.ComponentInteraction):
        """wether or not the interaction message is the same as the prvious paginator message"""
        return interaction.message.id == self.message_id

    @classmethod
    def from_custom_id(cls, custom_id: str):
        try:
            d = json.loads(custom_id)
            if not isinstance(d, Dict):
                raise TypeError
            custom_id_inst = cls(
                custom_id=d["cid"],
                type=d.get("t"),
                message_id=d.get("mid"),
                author_id=d.get("aid"),
                page=d.get("p"),
            )
            custom_id_inst._kwargs = {k:v for k, v in d.items() if k not in ["t", "cid", "mid", "aid", "p"]}
            return custom_id_inst
        
        except (TypeError, json.JSONDecodeError):
            return cls(custom_id=custom_id)

    def get(self, key: str) -> int|str|None:
        return self._kwargs.get(key)
    
    def set_position(self, position: int) -> "CustomID":
        self._position = position
        return self
    
    def add_kwarg(self, key: str, value: Any):
        self._kwargs[key] = value
    
    def serialize_custom_id(
        self,
    ) -> JsonDict:
        """

        Returns:
        --------
        str :
            The jsonified dict with following keys:
            * `t` str
                the type which was set in __init__ `custom_id_type` to specify use of paginator
            * `p` : int
                current page index
            * `cid`: str
                the `<custom_id>` to identify what to do
            - `aid`: int
                the `<author_id>` to identify later on the auther who used the interaction
            - `mid`: int
                the `<message_id>` to identify later on the message which was used
            - `kwargs`: Any
                optional additional kwargs

        Note:
        -----
            - custom_id has a max len of 100 chars
        """
        d = {
            "cid": self.custom_id,
            "t": self.type,
            "p": self.position
        }
        if self._author_id:
            d["aid"] = self._author_id
        if self._message_id:
            d["mid"] = self._message_id
        d.update(self._kwargs)
        log.debug(f"serialized custom_id: {d}")
        return JsonDict(d)
            
class NavigationMenuBuilder():
    _pages: int = 0
    _compact: bool = False
    _current_index: int = 0
    _disable_pagination: bool = False
    _additional_components: List[MessageActionRowBuilder] | None = None
    _button_rows: int = 4
    _disabled: bool = False

    def __init__(self, paginator: "Paginator"):
        self._paginator = paginator

    @property
    def paginator(self) -> "Paginator":
        return self._paginator

    @property
    def pages(self) -> int:
        return self._pages

    @property
    def compact(self) -> bool:
        return self._compact or len(self._paginator._pages) < 3

    @property
    def index(self) -> int:
        return self._current_index

    @property
    def disable_pagination(self) -> bool:
        return self._disable_pagination

    @property
    def additional_components(self) -> List[MessageActionRowBuilder] | None:
        return self._additional_components

    @property
    def button_rows(self) -> int:
        return self._button_rows
    
    @property
    def disabled(self) -> bool:
        return self._disabled



    def set_current_index(self, index: int):
        self._current_index = index

    def set_pages(self, pages: int):
        self._pages = pages

    def set_disable_pagination(self, disable_pagination: bool):
        self._disable_pagination = disable_pagination

    def set_additional_components(self, additional_components: List[MessageActionRowBuilder] | None):
        self._additional_components = additional_components

    def set_compact(self, compact: bool):
        self._compact = compact

    def from_paginator(self, paginator: "Paginator"):
        self._current_index = paginator._position
        self._pages = len(paginator._pages)

    def set_style(self, style: str):
        """
        sets the style of the navigation menu
        
        Args:
        -----
        style: str
            the style of the navigation menu
        
        Style Options:
        --------------
        classic:
            navigation with arrows
        numbers:
            navigation with numbers
        """

    def build(self) -> MessageActionRowBuilder:
        raise NotImplementedError
    

    def _navigation_row(self, position = None) -> Optional[List[MessageActionRowBuilder]]:
        if self.disabled:
            return None

        action_row = None
        if not self._compact:
            action_row = self._button_factory(
                custom_id="first", 
                emoji="⏮", 
                disable_when_index_is=lambda p: p == 0
            )
        if self.pages > 1:
            action_row = self._button_factory(
                custom_id="previous",
                emoji="◀",
                action_row_builder=action_row or MessageActionRowBuilder(),
                disable_when_index_is=lambda p: p == 0,
            )
        action_row = self._button_factory(
            custom_id="stop",
            emoji="✖",
            label=f"{self.index+1}/{self.pages}",
            action_row_builder=action_row,
            style=ButtonStyle.DANGER,
        )
        if self.pages > 1:
            action_row = self._button_factory(
                custom_id="next",
                emoji="▶",
                action_row_builder=action_row,
                disable_when_index_is=lambda p: p == self.pages-1,
            )
        if not self.compact:
            action_row = self._button_factory(
                custom_id="last",
                emoji="⏭",
                action_row_builder=action_row,
                disable_when_index_is=lambda p: p == self.pages-1,
            )

        return [action_row]
    
    def _number_button_navigation_row(self, position=None) -> Optional[List[MessageActionRowBuilder]]:
        # calculate start and stop indices for the three cases
        BUTTONS_PER_ROW = 5
        BUTTON_AMOUNT = self.button_rows * BUTTONS_PER_ROW
        if self.index < BUTTONS_PER_ROW * 2:
            # start at 0 because index is in the first two rows
            start = 0
            stop = min(BUTTON_AMOUNT, self.pages)
        else:
            # dont start at 0 because index is anywhere after the first two rows
            row_index = self.index // BUTTONS_PER_ROW
            if row_index < 2:
                start = 0
                stop = BUTTON_AMOUNT
            elif row_index > self.index // BUTTONS_PER_ROW - 2:
                stop = self.pages
                start = max(
                    ((stop - BUTTON_AMOUNT) // BUTTONS_PER_ROW + 1) * BUTTONS_PER_ROW, 
                    0
                )
            else:
                start = (row_index - 2) * BUTTONS_PER_ROW
                stop = start + BUTTON_AMOUNT

        action_rows = []
        for i in range(start, stop, BUTTONS_PER_ROW):
            action_row = MessageActionRowBuilder()
            for j in range(i, min(i+BUTTONS_PER_ROW, stop)):
                button_index = j - start
                action_row = self._button_factory(
                    custom_id= "stop" if j == self.index else f"pagination_page_{j}",  # pressing selected button will stop the paginator
                    label=str(j+1),
                    action_row_builder=action_row or MessageActionRowBuilder(),
                    # disable_when_index_is=lambda p: p == j,
                    style=ButtonStyle.PRIMARY if j == self.index else ButtonStyle.SECONDARY,
                )
            action_rows.append(action_row)
        return action_rows

    def _button_factory(
        self,
        disable_when_index_is: Callable[[Optional[int]], bool] = (lambda x: False),
        label: str = "",
        style = ButtonStyle.SECONDARY,
        custom_id: Optional[str] = None,
        emoji: Optional[str] = None,
        action_row_builder: Optional[MessageActionRowBuilder] = None,
        
    ) -> MessageActionRowBuilder:
        if action_row_builder is None:
            action_row_builder = MessageActionRowBuilder()
        state: bool = disable_when_index_is(self.index)
        if not custom_id:
            custom_id = label
        btn = InteractiveButtonBuilder(style=style, custom_id=custom_id)
        btn.set_is_disabled(state)
        if emoji:
            btn.set_emoji(emoji)

        if label:
            btn.set_label(label)
        action_row_builder.add_component(btn)
        return action_row_builder
        

class Paginator():
    def __init__(
        self,
        page_s: Union[List[Embed], List[str]],
        timeout: int = 2*60,
        component_factory: Callable[[int], MessageActionRowBuilder] | None = None,
        components_factory: Callable[[int], List[MessageActionRowBuilder]] | None = None,
        additional_components: List[MessageActionRowBuilder] | None = None,
        disable_pagination: bool = False,
        disable_component: bool = True,
        disable_components: bool = False,
        disable_paginator_when_one_site: bool = True,
        listen_to_events: List[Type[hikari.Event]] = [],
        compact: Optional[bool] = None,
        default_page_index: int = 0,
        download: Union[Callable[["Paginator"], str], str, bool] = False,
        download_name: str = "content.txt",
        disable_search_btn: bool = True,
        first_message_kwargs: Dict[str, Any] = {},
        custom_id_type: str | None = None,
        number_button_navigation: bool = False,
        number_button_rows: int = 4,
        hide_components_when_one_site: bool = False,
    ):
        """
        ### A Paginator with many options

        Args:
        -----
        pege_s: List[Embed] | List[str] 
            the page*s the Paginator should paginate
        timeout: int, default=120
            the seconds the paginator has to be inactive to "shutdown"; maximum is 15*60 min
        component_factory: Callable[[int], MessageActionRowBuilder], default=None
            a custom component builder; the input is the index of the site
        components_factory: Callable[[int], MessageActionRowBuilder], default=None
            a custom components builder; the input is the index of the site
        disable_component: bool, default=False
            wether or not the component of the paginator should be disabled
        disable_components: bool, default=False
            wether or not the components of the paginator should be disabled
        disable_paginator_when_one_site: bool, default=True
            wether or not the pagination should be disabled when the length of the pages is 1
        listen_to_events: List[hikari.Event]
            events the bot should listen to. These are needed to use them later with the `listener` decorator
        compact: bool
            display only necessary components (previous, stop, next)
        download: str | Callable[[Paginator], str] | bool, default=False
            - (str) this will be the content of the file
            - (Callable[[Paginator], str]) A function, which takes in `self` and returns the file content as string
            - (bool) If True, the pagination embeds|strings will be automatically convertet into a str; 
                        If False, deactivate download functionallity at all
        download_name: str
            the name of the download file
        first_message_kwargs: Dict[str, Any], default
            kwargs, which should be added to the first created message
        disable_search_btn: bool
            wether or not to disable the search button
        custom_id_type: str | None
            if str:
                custom_id will be converted to json with following keys:
                    - type -> `<custom_id_type>`
                    - custom_id -> the actual custom_id
                    - author_id -> the id of the person using this paginator
                    - message_id -> the id of the message of this paginator
                    **kwargs -> additional self defined keys and values
            if None:
                custom_id will be the bare custom_id not converted to json
        number_button_navigation: bool
            wether or not to use number buttons for navigation.
            Only used when len of pages below 20
        number_button_rows: int = 4
            How many button rows should be used if `number_button_navigation` is used
        Note:
        -----
            - the listener is always listening to 2 events:
                - GuildMessageCreateEvent (only when in context with the Paginator)
                - ComponentInteractionEvent (only component interaction, only when in context with the paginator)
                - PaginatorReadyEvent
            - create custom components with:
                either 
                - passing in `component(s)_factory`
                or
                - overriding `build_default_component(s)`; args: self, position (int)
            - to first_message_kwargs: this will add the kwargs, even if the kwargs are already in the method. So this could raise errors
        """
        global count
        count  += 1
        self.count = count
        self.onetime_kwargs = {}  # used once when sending a message
        self._stop: asyncio.Event = asyncio.Event()
        self._pages: Union[List[Embed], List[str]] = page_s
        self._old_position: int = 0

        self._component: Optional[MessageActionRowBuilder] = None
        self._components: Optional[List[MessageActionRowBuilder]] = None
        self._disable_components = disable_components
        self._disable_component = disable_component
        self._disable_search_btn = disable_search_btn
        if not self._disable_component and not self._disable_components:
            raise RuntimeError(f"Paginator.__init__: disable_component can be False OR disable_components can be False. Not both")
        self._disable_paginator_when_one_site = disable_paginator_when_one_site
        self._task: asyncio.Task
        self._message: Message
        self._component_factory = component_factory
        self._components_factory = components_factory
        self._default_page_index = default_page_index or 0
        self._download: Union[Callable[[Paginator], str], str, None] = download
        self._download_name = download_name
        self._first_message_kwargs = first_message_kwargs or {}
        self._additional_components = additional_components or []
        self._custom_id_type = custom_id_type
        self._number_button_navigation = number_button_navigation
        self.button_rows = number_button_rows
        self._with_update_button = False
        self._hide_components_when_one_site = hide_components_when_one_site

        self.bot: lightbulb.BotApp
        self._ctx: InteractionContext | None = None
        self._channel_id: int | None = None
        self._author_id: int | None = None

        self.listener = EventListener(self)
        self.log = getLogger(__name__, str(count))
        self.log.setLevel(LOGLEVEL)
        self.timeout = timeout
        self.listen_to_events = listen_to_events
        self._interaction: hikari.ComponentInteraction | None = None            
        self._stopped: bool = False         
        self._last_used: float = time.time()
        self._proxy: Optional[lightbulb.ResponseProxy] = None

        # paginator configuration
        self.pagination = not disable_pagination
        if self.pagination:
            self._position: int = 0
        if compact is None:
            self.compact = len(page_s) <= 1
        else:
            self.compact = compact
        

        # register all listeners
        for name, obj in type(self).__dict__.items():
            if isinstance(obj, EventObserver):
                obj = getattr(self, name)
                copy_obj = deepcopy(obj)  
                # why deepcopy?: the `obj` seems to be, no matter if pag is a new instance, always the same obj.
                # so it would add without deepcopy always the same obj with was configured in the first instance of `self.__cls__`
                copy_obj.name = name
                copy_obj.paginator = self
                self.listener.subscribe(copy_obj, copy_obj.event)
    @staticmethod
    def raise_or_return(attr: Any, attr_name: str):
        """raises if <`attr`> is None. Returnes otherwise"""
        if attr is None:
            raise TypeError(f"`{attr_name}` is None")
        return attr

    @property
    def channel_id(self) -> int:
        return self.raise_or_return(self._channel_id, "self._channel_id")

    @property
    def author_id(self) -> int:
        return self.raise_or_return(self._author_id, "self._author_id")

    @property
    def ctx(self) -> InuContext:
        return self.raise_or_return(self._ctx, "self._ctx")
    
    @ctx.setter
    def ctx(self, ctx: InuContext) -> None:
        self._ctx = ctx

    @property
    def pages(self):
        return self._pages

    @property
    def component(self) -> Optional[MessageActionRowBuilder]:
        if self._disable_component:
            return None
        if self._component_factory is not None:
            return self._component_factory(self._position)
        elif self._component is not None:
            return self._component
        elif hasattr(self, "build_default_component"):
            return getattr(self, "build_default_component")(self._position)
        else:
            raise RuntimeError((
                "Nothing specified for `component`. "
                "Consider passing in a component factory or set"
                "a value for `instance`._component"
                ))

    @property
    def components(self) -> List[MessageActionRowBuilder]:
        if self._disable_components:
            return []
        if self._components_factory is not None:
            return self._components_factory(self._position)
        elif self._components is not None:
            return self._components
        elif hasattr(self, "build_default_components"):
            return getattr(self, "build_default_components")(self._position)
        else:
            raise RuntimeError((
                "Nothing specified for `components`. "
                "Consider passing in a components_factory or set"
                "a value for `instance`._components"
            ))

    def interaction_pred(self, event: InteractionCreateEvent) -> bool:
        """Checks user and message id of the event interaction"""
        if not isinstance((i := event.interaction), ComponentInteraction):
            self.log.debug("False interaction pred")
            return False
        return (
            i.user.id == self.author_id
            and i.message.id == self._message.id
        )

    def wrong_button_click(self, event: InteractionCreateEvent):
        """checks if a user without permission clicked a button of this paginator"""
        return (
            isinstance(event.interaction, hikari.ComponentInteraction)  # is a button or menu
            and not self.interaction_pred(event)  # e.g. wrong author
            and event.interaction.message.id == self._message.id  # type: ignore # same message
        )

    def message_pred(self, event: MessageCreateEvent):
        msg = event.message
        return (
            msg.channel_id == self.channel_id
            and self.author_id == msg.author.id
        )

    def _button_factory(
        self,
        disable_when_index_is: Callable[[Optional[int]], bool] = (lambda x: False),
        label: str = "",
        style = ButtonStyle.SECONDARY,
        custom_id: Optional[str] = None,
        emoji: Optional[str] = None,
        action_row_builder: Optional[MessageActionRowBuilder] = None,
        
    ) -> MessageActionRowBuilder:
        if action_row_builder is None:
            action_row_builder = MessageActionRowBuilder()
        state: bool = disable_when_index_is(self._position)
        if not custom_id:
            custom_id = label
        btn = InteractiveButtonBuilder(style=style, custom_id=custom_id)
        btn.set_is_disabled(state)
        if emoji:
            btn.set_emoji(emoji)

        if label:
            btn.set_label(label)
        action_row_builder.add_component(btn)
        return action_row_builder

    def _navigation_row(self, position = None) -> Optional[List[MessageActionRowBuilder]]:
        if not self.pagination:
            return None

        rows: List[MessageActionRowBuilder] = []
        action_row = None
        if not self.compact:
            action_row = self._button_factory(
                custom_id="first", 
                emoji="⏮", 
                disable_when_index_is=lambda p: p == 0
            )
        if len(self._pages) > 1:
            action_row = self._button_factory(
                custom_id="previous",
                emoji="◀",
                action_row_builder=action_row or MessageActionRowBuilder(),
                disable_when_index_is=lambda p: p == 0,
            )
        action_row = self._button_factory(
            custom_id="stop",
            emoji="✖",
            label=f"{self._position+1}/{len(self._pages)}",
            action_row_builder=action_row,
            style=ButtonStyle.DANGER,
        )
        if len(self._pages) > 1:
            action_row = self._button_factory(
                custom_id="next",
                emoji="▶",
                action_row_builder=action_row,
                disable_when_index_is=lambda p: p == len(self.pages)-1,
            )
        if not self.compact:
            action_row = self._button_factory(
                custom_id="last",
                emoji="⏭",
                action_row_builder=action_row,
                disable_when_index_is=lambda p: p == len(self.pages)-1,
            )
        rows.append(action_row)
        if self._with_update_button:
            if len(action_row._components) >= 5:
                rows.append(MessageActionRowBuilder())
            rows[-1] = self._button_factory(
                custom_id="sync",
                emoji="🔁",
                action_row_builder=rows[-1],
            )
        return rows
    
    def _number_button_navigation_row(self, position=None) -> Optional[List[MessageActionRowBuilder]]:
        if not self.pagination:
            return None

        # calculate start and stop indices for the three cases
        BUTTONS_PER_ROW = 5
        BUTTON_AMOUNT = self.button_rows * BUTTONS_PER_ROW
        if self._position < BUTTONS_PER_ROW * 2:
            start = 0
            stop = min(BUTTON_AMOUNT, len(self._pages))
        else:
            row_index = self._position // BUTTONS_PER_ROW
            if row_index < 2:
                start = 0
                stop = BUTTON_AMOUNT
            elif row_index > len(self._pages) // BUTTONS_PER_ROW - 2:
                stop = len(self._pages)
                start = max(
                    ((stop - BUTTON_AMOUNT) // BUTTONS_PER_ROW + 1) * BUTTONS_PER_ROW, 
                    0
                )
            else:
                start = (row_index - 2) * BUTTONS_PER_ROW
                stop = start + BUTTON_AMOUNT

        action_rows = []
        for i in range(start, stop, BUTTONS_PER_ROW):
            action_row = MessageActionRowBuilder()
            for j in range(i, min(i+BUTTONS_PER_ROW, stop)):
                button_index = j - start
                action_row = self._button_factory(
                    custom_id= "stop" if j == self._position else f"pagination_page_{j}",  # pressing selected button will stop the paginator
                    label=str(j+1),
                    action_row_builder=action_row or MessageActionRowBuilder(),
                    # disable_when_index_is=lambda p: p == j,
                    style=ButtonStyle.PRIMARY if j == self._position else ButtonStyle.SECONDARY,
                )
            action_rows.append(action_row)
        return action_rows


    
    def build_default_component(self, position=None) -> Optional[MessageActionRowBuilder]:
        if self._disable_paginator_when_one_site and len(self._pages) == 1:
            return None
        return self._navigation_row(position)[0]
    
    def build_default_components(self, position=None) -> List[MessageActionRowBuilder]:
        action_rows = []
        if self._disable_paginator_when_one_site and len(self._pages) == 1:
            action_rows.extend(self._additional_components)
            return action_rows
        if self._number_button_navigation:
            # number navigation
            navi = self._number_button_navigation_row(position)
        else:
            # arrow navigation
            navi = self._navigation_row(position)
        if navi:
            action_rows.extend(navi)
        action_row = None
        if (
            not self.compact 
            and not self._disable_search_btn
            and not self._number_button_navigation
        ):
            action_row = self._button_factory(
                custom_id="search",
                emoji="🔍"
            )
            action_rows.append(action_row)
        if self._additional_components:
            action_rows.extend(self._additional_components)    
        return action_rows
    
    def add_page(self, page: Union[Embed, str]):
        self._pages.append(page)

    def add_onetime_kwargs(self, **kwargs):
        """
        Kwargs used when sending the next message.
        These will be cleared after the message is sent
        """
        self.onetime_kwargs.update(kwargs)
        
    async def move_to_page(self, index: int, ctx: InuContext | None = None):
        """
        Moves to the page on the given index.

        Args:
            index (int): The index of the page to move to.
            ctx (InuContext | None, optional): The context to use, if the paginator needs to restart.
        """
        if index < 0 or index >= len(self._pages):
            index = len(self._pages) - 1
        
        if self._stopped:
            self._position = index
            await self.start(ctx or self.ctx)
        else:
            await self.paginate(index)

    @property
    def download(self) -> Optional[str]:
        if not self._download:
            return None
        elif callable(self._download):
            return self._download(self)
        elif isinstance(self._download, str):
            return self._download
        elif isinstance(self._download, bool) and self._download is True:
            return self._pages_to_str()

    def _pages_to_str(self) -> str:
        text = ""
        if isinstance(self._pages[0], hikari.Embed):
            for embed in self._pages:
                text += self._embed_to_md(embed)  # type: ignore
        elif isinstance(self._pages[0], str):
            text = "\n".join(
                line for page in [textwrap.wrap(text, width=100) for page in self._pages] for line in page
            )
        else:
            raise RuntimeError(f"Can't convert `self._pages` of type {type(self._pages)} to str")
        return text

    @staticmethod
    def _embed_to_md(embed: hikari.Embed) -> str:
        """
        Converts an Embed to Markdown
        """
        text = ""
        if embed.title:
            text += f"# {embed.title}"
        if embed.description:
            text += "\n".join(textwrap.wrap(embed.description, 100))
        for field in embed.fields:
            text += f"\n## {field.name}"
            text += "\n".join(textwrap.wrap(field.value, 100))
        text += "\n----------------------------------------\n"
        return text
        
    async def defer_initial_response(self):
        await self.ctx.defer()

    def set_context(self, ctx: InuContext | None = None, event: hikari.Event | None = None) -> None:
        """
        create new context object `ctx` of paginator
        and resets `self._last_used` and with that the internal timeout

        Args:
        ----
        ctx: InuContext
            the context to use for sending messages
        events: hikari.Event
            the event to use to create the right ctx

        Raises:
        ------
        RuntimeError :
            - if `ctx` and `event` is None
            - when type of `event` is not supported
        """
        self._last_used = time.time()
        if not ctx:
            self.log.debug(f"fetch context for event {repr(event)}")
            ctx = get_context(event)
        # this way errors would occure, since responses etc would be resetted
        if self._ctx and ctx.id == self.ctx.id:
            return
        self.ctx = ctx
        #self.ctx._responses = responses


    async def send(
        self, 
        content: _Sendable, 
        interaction: Optional[ComponentInteraction] = None, 
        **kwargs
    ):
        """
        sends a message with current context and adds it's component(s)
        """
        if kwargs.get("update") is None:
            kwargs["update"] = True
        if not self._disable_component and not kwargs.get("component") and not (len(self.pages) == 1 and self._hide_components_when_one_site):
            kwargs["component"] = self.component
        elif not self._disable_components and not kwargs.get("components") and not (len(self.pages) == 1 and self._hide_components_when_one_site):
            kwargs["components"] = self.components

        if isinstance(content, str):
            kwargs["content"] = content
        elif isinstance(content, Embed):
            kwargs["embed"] = content  
        else:
            raise TypeError(f"<content> can't be an isntance of {type(content).__name__}")
        kwargs.update(self.onetime_kwargs)
        log.debug(f"Sending message: {kwargs}")
        proxy = await self.ctx.respond(**kwargs)
        self.onetime_kwargs.clear()
        self._proxy = proxy

    async def create_message(
            self, 
            content: str | None = None, 
            embed: str | None = None, 
            ephemeral: bool = True,
            auto_defer_update: bool = True,
            **kwargs
        ):
        """
        Args:
        ----
        content: str | None
            The message content to send
        embed: hikari.Embed | None
            The message embed to send
        ephemeral: bool
            wether or not only the interaction user should see the message
        auto_defer_update:
            wether or not to create a initial response with `hikari.ResponseType.DEFERRED_MESSAGE_UPDATE`
            if no initial response already done
        **kwargs: Any
            addidional kwargs which will be passed into `hikari.ComponentInteraction.execute`
        Note:
        -----
        if _initial_response_status is hikari.ResponseType.DEFERRED_MESSAGE_CREATE than this will create the
        response!

        Raises:
        ------
        RuntimeError:
            when auto_defer is off and initial response wasn't done yet
        """
        if ephemeral:
            kwargs["flags"] = hikari.MessageFlag.EPHEMERAL
        if content:
            kwargs["content"] = content
        if embed:
            kwargs["embed"] = embed
        await self.ctx.respond(update=False, **kwargs)


    async def stop(self, kwargs: Dict[str, Any] | None = None):
        """
        updates the message and removes all components

        Args:
        -----
        kwargs: Dict[str, Any] | None
            additional kwargs to pass into `hikari.Message.edit`
        """
        if self._stopped:
            return
        # to prevent from calling again
        self._stopped = True
        self.log.debug("stopping navigator")
        with suppress(NotFoundError, hikari.ForbiddenError):
            kwargs = kwargs or {}
            if self.components:
                kwargs["components"] = []
            elif self.component:
                kwargs["component"] = None
            await self.ctx.respond(**kwargs, update=True)
            # await self._message.remove_all_reactions()

    async def start(
        self, 
        ctx: InuContext,
        **kwargs,
    ) -> hikari.Message:
        """
        starts the pagination
        
        Args:
        -----
        ctx : Context
            the Context to use to send the first message
        message : int | hikari.Message | None
            An existing message to edit for the paginator


        Note:
        -----
        Requirements to use one_time_event:
            all custom_ids need to be converted to json.
            Following keys are required (*) or optional (-):
            `* t: str`
                the type of the custom_id, for example tag
            `* cid: str`
                the actual custom_id
            `* p: int`
                the page number where the paginator was
            `- mid: int`
                the message id of the pagination message used before
            `- aid: int`
                the id of the author who used the paginator
            also, this method should be overwrite to recreate the 
            messages from the custom id json
            
            
        Calls:
        ------
        - `self.post_start` - coro - when start finished
        Returns:
        -------
            - (hikari.Message) the message, which was used by the paginator
        """
        self._stopped = False
        if not isinstance(ctx, InuContext):
            self.log.debug("get context")
            self.ctx = get_context(ctx.event)
        else:
            self.log.debug("set context form given")
            self.ctx = ctx
        self._ctx._responded = ctx._responded
        log.debug(f"{type(self.ctx)}")
        self.bot = self.ctx.bot
        self._author_id = self.ctx.author.id
        self._channel_id = self.ctx.channel_id

        if len(self.pages) < 1:
            raise RuntimeError("<pages> must have minimum 1 item")
        elif len(self.pages) == 1 and self._disable_paginator_when_one_site and len(self.components) == 0:
            self.log.debug("<pages> has only one item, and <components> has only one item, so the paginator will exit")
            if isinstance(self.pages[0], Embed):
                msg_proxy = await self.ctx.respond(
                    embed=self.pages[0],
                    **self._first_message_kwargs
                )
            else:
                msg_proxy = await self.ctx.respond(
                    content=self.pages[0],
                    **self._first_message_kwargs
                )
            return await msg_proxy.message()

        if self._default_page_index < 0:
            self._default_page_index = len(self._pages) + self._default_page_index  # otherwise stop btn displays "0/x"
        if self._position in [None, 0]:
            self._position = self._default_page_index

        # make kwargs for first message
        kwargs.update(self._first_message_kwargs)
        if not self._disable_component and not (len(self.pages) == 1 and self._hide_components_when_one_site):
            kwargs["component"] = self.component
        elif not self._disable_components and not (len(self.pages) == 1 and self._hide_components_when_one_site):
            kwargs["components"] = self.components
        if (download := self.download):
            kwargs["attachment"] = hikari.Bytes(download, self._download_name)
        kwargs.update(self._first_message_kwargs)

        if isinstance(self.pages[self._default_page_index], Embed):
            self.log.debug("Creating message with embed")
            msg_proxy = await self.ctx.respond(
                embed=self.pages[0],
                **kwargs
            )
        else:
            self.log.debug(f"Creating message with content {self.pages[self._default_page_index]}")
            msg_proxy = await self.ctx.respond(
                content=self.pages[self._default_page_index],
                **kwargs
            )
        self._message = await msg_proxy.message()
        self._proxy = msg_proxy
        self.log.debug(f"Message created: {self._message.id}")
        # check for one extra component - paginator is automatically disabled when there is only one site
        if len(self.pages) == 1 and self._disable_paginator_when_one_site and len(self.components) < 1:
            self.log.debug("Only one page, exiting")
            return self._message
        self.log.debug(f"Starting pagination with message {repr(self._message)}")
        await self.post_start()
        return self._message

    async def post_start(self, **kwargs):
        """
        dispatches paginator ready event
        starts the pagination loop
        """
        try:
            await self.dispatch_event(PaginatorReadyEvent(self.bot))
            await self.pagination_loop(**kwargs)
        except Exception:
            self.log.error(traceback.format_exc())

    async def pagination_loop(self, **kwargs):
        try:
            def create_event(event, predicate: Callable | None = None):
                if predicate:
                    return self.bot.wait_for(
                        event,
                        timeout=self.timeout,
                        predicate=predicate
                    )
                else:
                    return self.bot.wait_for(
                        event,
                        timeout=self.timeout,
                    )
            

            while not self._stop.is_set():
                self.log.debug(f"re-enter pagination loop - status: {self._stop.is_set()}, {self.timeout=}")
                try:
                    # default events
                    events = [
                        create_event(InteractionCreateEvent),
                        self._stop.wait()
                    ]
                    # adding user specific events
                    for event in self.listen_to_events:
                        events.append(create_event(event))
                    # wait for first incoming event
                    done, pending = await asyncio.wait(
                        [asyncio.create_task(task) for task in events],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=self.timeout - (time.time() - self._last_used)
                    )
                except Exception:
                    log.error(traceback.format_exc())
                
                # timeout - no tasks done - stop
                if len(done) == 0:
                    self.log.debug(f"no done tasks - stop")
                    self.dispatch_event(PaginatorTimeoutEvent(self.bot))
                    self._stop.set()
                
                # cancel all other tasks
                for e in pending:
                    e.cancel()
                if self._stop.is_set():
                    continue

                # unpack Event
                event = done.pop().result()
                if not isinstance(event, hikari.Event):
                    log.error(f"Unknown result - not an instance of `hikari.Event`")
                    self._stop.set()
                    continue

                if (
                    isinstance(event, hikari.InteractionCreateEvent) 
                    and self.interaction_pred(event)
                    and (
                        event.interaction.custom_id in [
                            "first", "previous", "search",
                            "stop", "next", "last", 
                        ]
                        or event.interaction.custom_id.startswith(NUMBER_BUTTON_PREFIX)
                    )
                ):
                    self.set_context(event=event)

                self.log.debug(f"dispatch event | {self.count}")
                await self.dispatch_event(event)
            await self.stop()
            return
        except BotResponseError as e:
            raise e
        except Exception:
            self.log.error(
                f"following traceback was suppressed and pagination continued:\n{traceback.format_exc()}"
            )
            await self.pagination_loop(**kwargs)
            
    async def dispatch_event(self, event: Event, reject_interaction: bool = True):
        """
        Args:
        ----
        event : `hikari.Event`
            sends an event to all listeners
        
        Note:
        -----
        - `ComponentInteraction`s matching the predicate will be used for pagination if custom_id matches
        - `ComponentInteraction`s with not patching predicate but matching message will be responded with a REJECTION_MESSAGE
        """
        if isinstance(event, InteractionCreateEvent):
            if self.wrong_button_click(event) and reject_interaction:
                ctx = get_context(event)
                await ctx.respond(
                    random.choice(REJECTION_MESSAGES), ephemeral=True
                )
                return
            if self.interaction_pred(event):
                # paginate if paginator predicate is True
                await self.paginate(id=event.interaction.custom_id or None)  # type: ignore
        await self.listener.notify(event)

    async def paginate(self, id: str | KeyboardInterrupt):
        """
        paginates the message

        Args:
        -----
        id : str
            [first|previous|stop|next|last|search] -> checks for 
            these ids. If contained, then execute according method

        """
        last_position = self._position
        self._old_position = self._position
        self.log.debug(self._position)
        if isinstance(id, int):
            self._position = id
        elif id == "first":
            self._position = 0
        elif id == "previous":
            if self._position == 0:
                return
            self._position -= 1
        elif id == "stop":
            await self.delete_presence()
        elif id == "next":
            if self._position == (len(self.pages)-1):
                return
            self._position += 1
        elif id == "last":
            self._position = len(self.pages)-1
        elif id == "search":
            await self.ctx.defer()
            await self.search()
            return
        elif id.startswith(NUMBER_BUTTON_PREFIX):
            self._position = int(id.replace(NUMBER_BUTTON_PREFIX, ""))
        if last_position != self._position or str(id) == "sync":
            await self._update_position()

    async def delete_presence(self):
        """Deletes this message, and invokation message, if invocation was in a guild"""
        if not self.ctx._responded:
            await self.stop()
        await self._proxy.delete()
        #await self.ctx.delete_webhook_message(self._message)

    async def _update_position(self, interaction: ComponentInteraction | None = None):
        """sends the page with the current `self._position` index"""
        await self.send(content=self.pages[self._position], interaction=interaction)
        
    async def search(self):
        bot_message = await self.ctx.respond("What do you want to search ?")
        try:
            message = await self.bot.wait_for(
                MessageCreateEvent,
                90,
                lambda e: e.author_id == self.author.id and e.channel_id == self.ctx.channel_id
            )
            query = str(message.content)
        except:
            return
        if isinstance(self.pages[0], hikari.Embed):
            site = self._search_embed(query)
        else:
            site = self._search_str(query)
        if site == -1:
            await self._message.respond(f"Nothing with `{query}` found")
            return
        await self.bot.rest.delete_messages(self.ctx.channel_id, [message.message_id, (await bot_message.message()).id])
        self._position = site
        await self.send(content=self.pages[self._position])
            
    def _search_embed(self, query: str) -> int:
        for i, e in enumerate(self.pages):
            if query in str(e.title) or query in str(e.description):
                return i
            for field in e.fields:
                if query in str(field.name) or query in str(field.value):
                    return i
        return -1
    
    def _search_str(self, query: str) -> int:
        for i, s in enumerate(self.pages):
            if query in str(s):
                return i
        return -1
            
            

    # usage
    # @listener(InteractionCreateEvent)
    # async def on_interaction(self, event):
    #     print("interaction received")

    # @listener(GuildMessageCreateEvent)
    # async def on_message(self, event):
    #     print("message received")

            

def navigation_row(
    position: int, 
    len_pages: int,
    compact: bool = False,
    custom_id_serializer: Callable[[str], str] = lambda c: c,
) -> MessageActionRowBuilder:
    """
    Creates the AcionRowBuilder for the navigation row

    Args:
    ----
    position : int
        for current page information and for checking for last or first page
    len_pages : int
        for last page information and for checking last page
    compact : bool
        wether or not to include last and first button
    custom_id_serializer : Callable[[str], str]
        A method which takes in the custom_id and returns the serialized custom_id.
        Per default the custom_id will be returned as is.
    """
    def button_factory( 
        disable_when_index_is: Callable[[Optional[int]], bool] = (lambda x: False),
        label: str = "",
        style = ButtonStyle.SECONDARY,
        custom_id: Optional[str] = None,
        emoji: Optional[str] = None,
        action_row_builder: MessageActionRowBuilder = MessageActionRowBuilder(),
        
    ) -> MessageActionRowBuilder:
        state: bool = disable_when_index_is(position)
        if not custom_id:
            custom_id = label
        btn = InteractiveButtonBuilder(style=style, custom_id=custom_id)
        btn.set_is_disabled(state)
        if emoji:
            btn.set_emoji(emoji)

        if label:
            btn.set_label(label)
        action_row_builder.add_component(btn)
        return action_row_builder
    

    action_row = None
    if not compact:
        action_row = button_factory(
            custom_id="first", 
            emoji="⏮", 
            disable_when_index_is=lambda p: p == 0
        )
    action_row = button_factory(
        custom_id="previous",
        emoji="◀",
        action_row_builder=action_row or MessageActionRowBuilder(),
        disable_when_index_is=lambda p: p == 0,
    )
    button_factory(
        custom_id="stop",
        emoji="✖",
        action_row_builder=action_row,
        style=ButtonStyle.DANGER,
    )
    button_factory(
        custom_id="next",
        emoji="▶",
        action_row_builder=action_row,
        disable_when_index_is=lambda p: p == len_pages-1,
    )
    if not compact:
        button_factory(
            custom_id="last",
            emoji="⏭",
            action_row_builder=action_row,
            disable_when_index_is=lambda p: p == len_pages-1,
        )

    return action_row

PagSelf = TypeVar("PagSelf", bound="StatelessPaginator")


class StatelessPaginator(Paginator, ABC):
    """
    A paginator which recreates the previous state out of the interacion custom_id.
    
    Abstract methods:
    -----------------
    `:obj:self._get_custom_id_kwargs(self)` : `Dict[str, int|str]`
        method which returns importent kwargs which need to be appended in custom_id json
    `:obj:self._rebuild(self, **kwargs)` : `None`
        coro which needs to call following methods:
            `:obj:self.set_pages(self, pages: List[str|Embed])` : `None`
                to set `self._pages`
            `:obj:self.set_context(ctx: Cotnext, event: Event)` : `None`
                to set `self.ctx` and `self.custom_id`

    Abstract properties:
    --------------------
    `:obj:self.custom_id_type` : `str`
        returns the type of the custom id to destinglish all stl pags

    Important methods:
    ------------------
    `:obj:self._rebuild()` : None
        rebuild the paginator pages and ctx with this method
    `:obj:self.rebuild()` : None
        use this method from outside to rebuild a paginator
    `:obj:self.start(self, ctx: Context)` : None
        method to firstly start the paginator. Override and call super()
    `:obj:self._serialize_custom_id(self, ...)` : str
        pass in the normal custom_id and get the json version with all information for stateless rebuilding
    `:obj:self.set_custom_id(self, custom_id: str)` : `None`
        intented to use as builder when rebuilding the paginator
    """
    def __init__(
        self,
        **kwargs

    ):
        self._custom_id: str | None = None
        kwargs.setdefault("page_s", [])
        super().__init__(**kwargs)

    async def start(
        self,
        ctx: InuContext,
        **kwargs,
    ) -> hikari.Message:
        """
        Args:
        -----
        ctx : Context
            the context to use to create messages

        Note:
        ----
            -   after the event was fired and processed (for example ComponentInteraction -> pagination -> next_page)
                the paginator will exit. No event listening will be done!
            -   Subclasses of this class should recreate the embeds here and pass them into `set_pages(pages: List[hikari.Embed | str])`
        """
        # custom_id provided -> edit old message
        # ctx could have been already set in a overridden subclass
        if not self._ctx:
            self.set_context(ctx)
        self._author_id = self.ctx.author.id
        self._channel_id = self.ctx.channel_id
        # kwargs passed when next message is created
        
        self.bot = self.ctx.bot
        return await super().start(ctx)

        
    def set_pages(self, pages: List[hikari.Embed] | List[str]):
        self._pages = pages

    @property
    def custom_id(self) -> CustomID:
        return CustomID.from_custom_id(self._custom_id or self.ctx.custom_id)
    
    @custom_id.setter
    def custom_id(self, value: str) -> None:
        self._custom_id = value

    @abstractmethod
    def _get_custom_id_kwargs(self) -> Dict[str, int|str]:
        """
        define a Dict with all needed extra keys and values to recreate the last state


        Returns:
        -------
        Dict[str, str | int]
            dict with all needed extra values to recreate the last state. (e.g. tag_id for tags)
        """
        ...
    @property
    @abstractmethod
    def custom_id_type(self) -> str:
        "the custom_id type to sort the custom_ids into a specific category"
        ...

    def _serialize_custom_id(
        self, 
        custom_id: str, 
        with_author_id: bool = True, 
        with_message_id: bool = True, 
        **kwargs
    ) -> str:
        """
        Args:
        -----
        custom_id: str
            the custom id for that component
        author_id : bool
            wether or not to include the author id
        message_id : bool
            wether or not to include the message id
        **kwargs : Dict[Any, Any]
            additional kwargs to add

        Returns:
        --------
        str :
            The jsonified dict with following keys:
            * `t` str
                the type which was set in __init__ `custom_id_type` to specify use of paginator
            * `p` : int
                current page index
            * `cid`: str
                the `<custom_id>` to identify what to do
            - `aid`: int
                the `<author_id>` to identify later on the auther who used the interaction
            - `mid`: int
                the `<message_id>` to identify later on the message which was used
            - `kwargs`: Any
                optional additional kwargs

        Note:
        -----
            - custom_id has a max len of 100 chars
        """
        kwargs.update(self._get_custom_id_kwargs())
        d = self._get_serialization_custom_id_dict(
            custom_id=custom_id,
            custom_id_type=self.custom_id_type,
            position=self._position,
            author_id=self.ctx.author.id if with_author_id else None,
            **kwargs
        )
        return json.dumps(d, indent=None, separators=(',', ':'))
    
    @staticmethod
    def _get_serialization_custom_id_dict(
        custom_id: str,
        custom_id_type: str,
        position: int,
        author_id: Optional[int] = None,
        message_id: Optional[int] = None,
        **kwargs
    ) -> Dict:
        """
        Manually serialize custom ID statically.
        
        Returns:
        - str: the serialized json string
        """
        d = {
            "cid": custom_id,
            "t": custom_id_type,
            "p": position
        }
        if author_id:
            d["aid"] = author_id
        if message_id:
            d["mid"] = message_id
        d.update(kwargs)
        return d
        
    async def dispatch_event(self, event: Event):
        """
        Override:
        ---------
        - id needs to be passed differently to paginate
        """
        if isinstance(event, InteractionCreateEvent) and self.interaction_pred(event):
            await self.paginate(id=self.custom_id.custom_id)
        await self.listener.notify(event)

    def _button_factory(
        self,
        disable_when_index_is: Callable[[Optional[int]], bool] = (lambda x: False),
        label: str = "",
        style = ButtonStyle.SECONDARY,
        custom_id: Optional[str] = None,
        emoji: Optional[str] = None,
        action_row_builder: Optional[MessageActionRowBuilder] = None,
        
    ) -> MessageActionRowBuilder:
        """
        Builds buttons

        Override:
        ---------
        - custom id gets in this paginator serialized to json
        """
        if action_row_builder is None:
            action_row_builder = MessageActionRowBuilder()
        state: bool = disable_when_index_is(self._position)
        if not custom_id:
            custom_id = label
        btn = InteractiveButtonBuilder(style=style, custom_id=self._serialize_custom_id(custom_id))
        btn.set_is_disabled(state)
        if emoji:
            btn.set_emoji(emoji)

        if label:
            btn.set_label(label)
        action_row_builder.add_component(btn)
        return action_row_builder

    async def post_start(self, events: List[hikari.Event] = [], **kwargs):
        """
        Args:
        -----
        events : List[hikari.Event]
            Events to fire in this instance


        Override:
        ---------
        - pass event into pagination_loop
        
        dispatches paginator ready event
        starts the pagination loop
        """
        try:
            await self.dispatch_event(PaginatorReadyEvent(self.bot))
            for e in events:
                await self.pagination_loop(event=e)
        except Exception:
            self.log.error(traceback.format_exc())

    async def pagination_loop(self, event: hikari.Event):
        """
        Override:
        --------
        - event waiting functionality fully removed
        - only dispatch given event
        """
        #if self.is_stateless:
        self.log.debug("dispatch event")
        await self.dispatch_event(event)

    def set_custom_id(self: PagSelf, custom_id: str) -> PagSelf:
        """
        This is intended to be used as builder method before starting the paginator.
        e.g. `await (StatelessPaginator().set_custom_id(custom_id)).start(event)`
        this is needed, that the start() coroutine can already use the custom_id
        """
        self.custom_id = custom_id  # type: ignore
        return self

    async def check_user(self) -> bool:
        """
        Returns wether or not the user is allowed to use this
        """
        if not self.custom_id.is_same_user(self.ctx.interaction):
            await self.ctx.respond(self._get_rejection_message(), ephemeral=True)
            return False
        return True
    
    def _get_rejection_message(self) -> str:
        return random.choice(REJECTION_MESSAGES)

    @abstractmethod
    async def _rebuild(self, **kwargs):
        ...

    async def rebuild(self, event: hikari.Event, reject_user: bool = True, **kwargs) -> None:
        """
        this method is called for restarting stateless pags

        Args:
        ----
        event : hikari.Event
            the event to fire
        """
        await self._rebuild(event=event, **kwargs)
        if (
            self._ctx is None
            or self.custom_id is None
            or self.custom_id_type is None
        ):
            raise TypeError("Needed attibutes for `StatelessPaginator.rebuild` or` None`") 
        # if reject_user:
        #     if not await self.check_user():
        #         # user is not allowed to use this
        #         return
        self.log.debug("set attrs")
        self._channel_id = self.ctx.channel_id
        self._author_id = self.custom_id.author_id
        self._message = self.ctx.original_message
        self._position = self.custom_id.page
        self.bot = self.ctx.bot
        self.log.debug("post start")
        await self.post_start(events=[event])


    async def delete_presence(self):
        """Deletes this message, and invokation message, if invocation was in a guild"""
        if not self.ctx._responded:
            await self.stop()
        await self.ctx.delete_initial_response()

    

