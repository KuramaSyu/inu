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
)
import json
import traceback
import logging
from abc import abstractmethod, ABCMeta, ABC
from copy import deepcopy
import textwrap

import hikari
from hikari.embeds import Embed
from hikari.messages import Message
from hikari.impl import MessageActionRowBuilder
from hikari import ButtonStyle, ComponentInteraction, GuildMessageCreateEvent, InteractionCreateEvent, MessageCreateEvent, NotFoundError, ResponseType
from hikari.events.base_events import Event
import lightbulb
from lightbulb.context import Context

from core import InteractionContext, RESTContext, InuContext, get_context, BotResponseError

log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)

__all__: Final[List[str]] = ["Paginator", "BaseListener", "BaseObserver", "EventListener", "EventObserver"]
_Sendable = Union[Embed, str]
T = TypeVar("T")

count = 0

class PaginatorReadyEvent(hikari.Event):
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
    def subscribe(self):
        pass
    
    @abstractmethod
    def unsubscribe(self):
        pass

    @abstractmethod
    async def notify(self):
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



class CustomID():
    __slots__ = ["_type", "_custom_id", "_message_id", "_author_id", "_kwargs", "_page"]
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

    def _raise_none_error(self, var_name: str):
        raise TypeError(f"`{self.__class__.__name__}.{var_name}` is None. Make sure, to set it!")

    @property
    def type(self) -> str:
        if self._type is None:
            self._raise_none_error("_type")
        return self._type

    @property
    def page(self) -> str:
        if self._page is None:
            self._raise_none_error("_page")
        return self._page
    
    @property
    def custom_id(self) -> str:
        if self._custom_id is None:
            self._raise_none_error("_custom_id")
        return self._custom_id

    @property
    def message_id(self) -> int:
        if self._message_id is None:
            self._raise_none_error("_message_id")
        return self._message_id
    
    @property
    def author_id(self) -> str:
        if self._author_id is None:
            self._raise_none_error("_author_id")
        return self._author_id

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
            custom_id = cls(
                custom_id=d["cid"],
                type=d.get("t"),
                message_id=d.get("mid"),
                author_id=d.get("aid"),
                page=d.get("p"),
            )
            custom_id._kwargs = {k:v for k, v in d.items() if k not in ["t", "cid", "mid", "aid", "p"]}
            return custom_id
        
        except (TypeError, json.JSONDecodeError):
            return cls(custom_id=custom_id)
        

class Paginator():
    def __init__(
        self,
        page_s: Union[List[Embed], List[str]],
        timeout: int = 2*60,
        component_factory: Callable[[int], MessageActionRowBuilder] = None,
        components_factory: Callable[[int], List[MessageActionRowBuilder]] = None,
        additional_components: List[MessageActionRowBuilder] = None,
        disable_pagination: bool = False,
        disable_component: bool = True,
        disable_components: bool = False,
        disable_paginator_when_one_site: bool = True,
        listen_to_events: List[Any] = [],
        compact: Optional[bool] = None,
        default_site: Optional[int] = 0,
        download: Union[Callable[["Paginator"], str], str, bool] = False,
        download_name: str = "content.txt",
        disable_search_btn: bool = False,
        first_message_kwargs: Dict[str, Any] = {},
        custom_id_type: str | None = None,
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
        self._stop: asyncio.Event = asyncio.Event()
        self._pages: Union[List[Embed], List[str]] = page_s

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
        self._default_site = default_site
        self._download: Union[Callable[[Paginator], str], str, None] = download
        self._download_name = download_name
        self._first_message_kwargs = first_message_kwargs or {}
        self._additional_components = additional_components or []
        self._custom_id_type = custom_id_type

        self.bot: lightbulb.BotApp
        self._ctx: InteractionContext | None = None
        self._channel_id: int | None = None
        self._author_id: int | None = None

        
        self.listener = EventListener(self)
        self.log = log
        self.timeout = timeout
        self.listen_to_events = listen_to_events
        self._interaction_response_status: hikari.ResponseType | None = None
        self._interaction: hikari.ComponentInteraction | None = None

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

    # @property
    # def interaction(self) -> hikari.ComponentInteraction | None:
    #     return self._interaction

    @property
    def ctx(self) -> InuContext:
        #assert (isinstance(self._ctx, InuContext) or isinstance(self._ctx, lightbulb.Context))
        return self.raise_or_return(self._ctx, "self._ctx")
    
    @ctx.setter
    def ctx(self, ctx: InuContext) -> None:
        #assert (isinstance(self._ctx, InuContext) or isinstance(self._ctx, lightbulb.Context))
        self._ctx = ctx

    # @interaction.setter
    # def interaction(self, value) -> None:
    #     self.log.debug(f"set interaction")
    #     self._interaction = value
    #     self.responded = None
    
    @property
    def custom_id_prefix(self) -> str:
        """The prefix which should be added before every custom_id"""
        return self._custom_id_prefix

    # @property
    # def responded(self) -> bool:
    #     return self._interaction_response_status is not None

    # @responded.setter
    # def responded(self, value) -> None:
    #     self.log.debug(f"update responsed to: {value} from {self._interaction_response_status}")
    #     self._interaction_response_status = value

    # def defered_responded(self) -> bool:
    #     return self._interaction_response_status in [hikari.ResponseType.DEFERRED_MESSAGE_UPDATE, hikari.ResponseType.DEFERRED_MESSAGE_CREATE]
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





    def interaction_pred(self, event: InteractionCreateEvent):
        if not isinstance((i := event.interaction), ComponentInteraction):
            self.log.debug("False interaction pred")
            return False
        return (
            i.user.id == self.author_id
            and i.message.id == self._message.id
        )

    def wrong_button_click(self, event: InteractionCreateEvent):
        """checks if a user without permission clicked a button of this paginator"""
        if not isinstance((i := event.interaction), ComponentInteraction):
            self.log.debug("False interaction pred")
            return False
        return (
            i.user.id != self.author_id
            and i.message.id == self._message.id
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
    
        btn = (
            action_row_builder
            .add_button(style, custom_id)
            .set_is_disabled(state)
        )
        if emoji:
            btn = btn.set_emoji(emoji)

        if label:
            btn = btn.set_label(label)
        btn = btn.add_to_container()
        return btn

    def _navigation_row(self, position = None) -> Optional[MessageActionRowBuilder]:
        if not self.pagination:
            return None


        action_row = None
        if not self.compact:
            action_row = self._button_factory(
                custom_id="first", 
                emoji="⏮", 
                disable_when_index_is=lambda p: p == 0
            )
        action_row = self._button_factory(
            custom_id="previous",
            emoji="◀",
            action_row_builder=action_row or MessageActionRowBuilder(),
            disable_when_index_is=lambda p: p == 0,
        )
        self._button_factory(
            custom_id="stop",
            emoji="✖",
            label=f"{self._position+1}/{len(self._pages)}",
            action_row_builder=action_row,
            style=ButtonStyle.DANGER,
        )
        self._button_factory(
            custom_id="next",
            emoji="▶",
            action_row_builder=action_row,
            disable_when_index_is=lambda p: p == len(self.pages)-1,
        )
        if not self.compact:
            self._button_factory(
                custom_id="last",
                emoji="⏭",
                action_row_builder=action_row,
                disable_when_index_is=lambda p: p == len(self.pages)-1,
            )

        return action_row
    
    def build_default_component(self, position=None) -> Optional[MessageActionRowBuilder]:
        if self._disable_paginator_when_one_site and len(self._pages) == 1:
            return None
        return self._navigation_row(position)
    
    def build_default_components(self, position=None) -> Optional[List[Optional[MessageActionRowBuilder]]]:
        navi = self.build_default_component(position)
        action_rows = []
        if navi:
            action_rows.append(navi)
        action_row = None
        if not self.compact and not self._disable_search_btn:
            action_row = self._button_factory(
                custom_id="search",
                emoji="🔍"
            )
            action_rows.append(action_row)
        if self._additional_components:
            action_rows.extend(self._additional_components)    
        return action_rows
    
    @property
    def download(self) -> Optional[str]:
        if not self._download:
            return None
        elif isinstance(self._download, Callable):
            return self._download(self)
        elif isinstance(self._download, str):
            return self._download
        elif isinstance(self._download, bool) and self._download is True:
            return self._pages_to_str()

    def _pages_to_str(self) -> str:
        text = ""
        if isinstance(self._pages, List[Embed]):
            for embed in self._pages:
                text += self._embed_to_md(embed)
        elif isinstance(self._pages, List[str]):
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
            text += "\n#### ".textwrap.wrap(embed.description, 100)
        for field in embed.fields:
            text += f"\n## {field.name}"
            text += "\n#### ".textwrap.wrap(field.value, 100)
        text += "\n----------------------------------------\n"
        return text
        
    async def defer_initial_response(self):
        await self.ctx.defer()

    def set_context(self, ctx: Context | None = None, event: hikari.Event | None = None) -> None:
        """
        create new context object `ctx` of paginator

        Args:
        ----
        ctx: lightbulb.Context
            the context to use for sending messages
        events: hikari.Event
            the event to use to create the right ctx

        Raises:
        ------
        RuntimeError :
            - if `ctx` and `event` is None
            - when type of `event` is not supported
        """
        if not ctx:
            ctx = get_context(event)
        # this way errors would occure, since responses etc would be resetted
        if self._ctx and ctx.interaction.id == self.ctx.interaction.id:
            return
        self.ctx = ctx
        #self.ctx._responses = responses


    async def send(
        self, 
        content: _Sendable, 
        interaction: Optional[ComponentInteraction] = None, 
    ):
        """
        
        """
        kwargs: Dict[str, Any] = {}
        if not self._disable_component:
            kwargs["component"] = self.component
        elif not self._disable_components:
            kwargs["components"] = self.components
        

        # if self._download:
        #     kwargs["attachments"] = [hikari.Bytes(self.download, "content")]

        if isinstance(content, str):
            kwargs["content"] = content
        elif isinstance(content, Embed):
            kwargs["embed"] = content  
        else:
            raise TypeError(f"<content> can't be an isntance of {type(content).__name__}")
        log.debug(f"Sending message: {kwargs}")
        await self.ctx.respond(update=True, **kwargs)

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


    async def stop(self):
        self._stop.set()
        with suppress(NotFoundError, hikari.ForbiddenError):
            kwargs = {}
            if self.components:
                kwargs["components"] = []
            elif self.component:
                kwargs["component"] = None
            await self.ctx.respond(**kwargs, update=True)
            # await self._message.remove_all_reactions()

    async def start(
        self, 
        ctx: Context,
        message: int | hikari.Message | None = None,
        events: List[hikari.Event] = [],
        paginator_config: Dict[str, Any] | None = None,
    ) -> hikari.Message:
        """
        starts the pagination
        
        Args:
        -----
        ctx : Context
            the Context to use to send the first message
        message : int | hikari.Message | None
            An existing message to edit for the paginator
        events : List[hikari.Event]
            Will fire given events in pagination loop and then exit
        paginator_config : Dict[str, Any] | None
            A dict used with one_time_event to define following things:
            - page: int - current page


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
            log.debug("<pages> has only one item, and <components> has only one item, so the paginator will exit")
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

        self._position = 0
        kwargs = self._first_message_kwargs
        if not self._disable_component:
            kwargs["component"] = self.component
        elif not self._disable_components:
            kwargs["components"] = self.components
        if (download := self.download):
            kwargs["attachment"] = hikari.Bytes(download, self._download_name)
        kwargs.update(self._first_message_kwargs)
        if isinstance(self.pages[self._default_site], Embed):
            msg_proxy = await self.ctx.respond(
                embed=self.pages[0],
                **kwargs
            )
        else:
            msg_proxy = await self.ctx.respond(
                content=self.pages[self._default_site],
                **kwargs
            )
        self._message = await msg_proxy.message()
        log.debug(f"Message created: {self._message.id}")
        # check for one extra component - paginator is automatically disabled when there is only one site
        if len(self.pages) == 1 and self._disable_paginator_when_one_site and len(self.components) < 1:
            self.log.debug("Only one page, exiting")
            return self._message
        self._position = 0
        self.log.debug("Starting pagination")
        self.log.debug(f"{self._message=}")
        await self.post_start(events=events)
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
            def create_event(event, predicate: Callable = None):
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
                self.log.debug("re-enter pagination loop")
                try:
                    events = [
                        create_event(InteractionCreateEvent),  # , self.interaction_pred
                        create_event(GuildMessageCreateEvent, self.message_pred),
                        self._stop.wait()
                    ]
                    # adding user specific events
                    for event in self.listen_to_events:
                        events.append(create_event(event))
                    done, pending = await asyncio.wait(
                        [asyncio.create_task(task) for task in events],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=self.timeout
                                    )
                except asyncio.TimeoutError:
                    self._stop.set()
                    return
                # maybe called from outside
                for e in pending:
                    e.cancel()
                if self._stop.is_set():
                    return
                try:
                    event = done.pop().result()
                    self.set_context(event=event)
                except Exception:
                    self._stop.set()
                    break
                self.log.debug(f"dispatch event | {self.count}")
                await self.dispatch_event(event)
            await self.stop()
        except Exception:
            self.log.error(traceback.format_exc())
            
    async def dispatch_event(self, event: Event):
        if isinstance(event, InteractionCreateEvent):
            if self.wrong_button_click(event):
                log.debug(self._message.id)
                await self.ctx.respond("Doesn't really looks like your menu, don't you think?", ephemeral=True)
                return
            await self.paginate(id=event.interaction.custom_id or None)
        await self.listener.notify(event)

    async def paginate(self, id: str):
        """
        paginates the message

        Args:
        -----
        id : str
            [first|previous|stop|next|last|search] -> checks for 
            these ids. If contained, then execute according method

        """
        last_position = self._position

        if id == "first":
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

        if last_position != self._position:
            await self._update_position()

    async def delete_presence(self):
        """Deletes this message, and invokation message, if invocation was in a guild"""
        if not self.ctx._responded:
            await self.stop()
        await self.ctx.interaction.delete_initial_response()

    async def _update_position(self, interaction: ComponentInteraction | None = None):
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
        if not emoji:
            btn = (
                action_row_builder
                .add_button(style, custom_id_serializer(custom_id))
                .set_is_disabled(state)
                .set_label(label)
                .add_to_container()
            )
        else:
            btn = (
                action_row_builder
                .add_button(style, custom_id_serializer(custom_id))
                .set_is_disabled(state)
                .set_emoji(emoji)
                .add_to_container()
            )
        return btn

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
        method which returns importend kwargs which need to be appended in custom_id json
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
        ctx: InuContext | Context | None = None,
    ):
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
        self.bot = self.ctx.bot
        return await super().start(ctx)

    def set_pages(self, pages: List[hikari.Embed | str]):
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
        d = {
            "cid": custom_id, 
            "t": self.custom_id_type,
            "p": self._position
        }
        if with_author_id:
            d["aid"] = self.ctx.author.id
        d.update(self._get_custom_id_kwargs())
        # if with_message_id:
        #     d["mid"] = self._message.id
        d.update(kwargs)
        return json.dumps(d, indent=None, separators=(',', ':'))

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
    
        btn = (
            action_row_builder
            .add_button(style, self._serialize_custom_id(custom_id))
            .set_is_disabled(state)
        )
        if emoji:
            btn = btn.set_emoji(emoji)

        if label:
            btn = btn.set_label(label)
        btn = btn.add_to_container()
        return btn

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
        log.debug("dispatch event")
        await self.dispatch_event(event)

    def set_custom_id(self: PagSelf, custom_id: str) -> PagSelf:
        """
        This is intended to be used as builder method before starting the paginator.
        e.g. `await (StatelessPaginator().set_custom_id(custom_id)).start(event)`
        this is needed, that the start() coroutine can already use the custom_id
        """
        self.custom_id = custom_id
        return self

    async def check_user(self) -> None:
        """
        Raises:
        -------
        AssertionError :
            when the user from the custom_id not matches with the one from the current context
        """
        if not self.custom_id.is_same_user(self.ctx.interaction):
            await self.ctx.respond("REJECTED - you are not really the ower of this", ephemeral=True)
            raise AssertionError("custom id user is not the same as interaction author")

    @abstractmethod
    async def _rebuild(self, **kwargs):
        ...

    async def rebuild(self, event: hikari.Event, **kwargs) -> None:
        """
        this method is called for restarting stateless pags

        Args:
        ----
        event : hikari.Event
            the event to fire
        """
        await self._rebuild(event=event, **kwargs)
        assert self._ctx is not None
        assert self.custom_id is not None
        assert self.custom_id_type is not None
        await self.check_user()
        log.debug("set attrs")
        self._channel_id = self.ctx.channel_id
        self._author_id = self.custom_id.author_id
        self._message = self.ctx.original_message
        self._position = self.custom_id.page
        self.bot = self.ctx.bot
        log.debug("post start")
        await self.post_start(events=[event])

    

