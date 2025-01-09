import asyncio
from collections import defaultdict
import datetime
from email.message import Message
import importlib
from optparse import Option
import os
import traceback
import typing
from typing import *
import logging
from asyncpraw.config import Config
from hikari.events.interaction_events import InteractionCreateEvent
from hikari.interactions.component_interactions import ComponentInteraction
from hikari import GatewayBot, ModalInteraction
from copy import copy

import lightbulb
import hikari
from hikari.snowflakes import Snowflakeish
from hikari.impl import ModalActionRowBuilder, TextInputBuilder
from hikari import TextInputStyle
import lavalink_rs
from dotenv import dotenv_values
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from colorama import Fore, Style
from matplotlib.colors import cnames
from numpy import mod
import tabulate

from .singleton import Singleton

from ._logging import LoggingHandler, getLogger, getLevel 
from . import ConfigProxy, ConfigType
from . import Bash

T_STR_LIST = TypeVar("T_STR_LIST", list[str], str)
T = TypeVar("T")

log = getLogger(__name__)
ALLOWED_EXTENSIONS = ["basics", "errors", "counter", "tags", "maths", "games", "statistics", "settings"]

class BotResponseError(Exception):
    def __init__(self, bot_message: Optional[str]=None, ephemeral: bool = False, **kwargs) -> None:
        self.kwargs: Dict[str, Any] = {}
        self.kwargs.update(kwargs)
        if bot_message:
            self.kwargs["content"] = bot_message
        if ephemeral:
            self.kwargs["flags"] = hikari.MessageFlag.EPHEMERAL
        self.bot_message = bot_message
        super().__init__()

    @property
    def context_kwargs(self) -> Dict[str, Any]:
        """
        Creates context kwargs for InuContext
        """
        context_kwargs = {}
        context_kwargs.update(self.kwargs)
        if context_kwargs.get("flags") == hikari.MessageFlag.EPHEMERAL:
            del context_kwargs["flags"]
            context_kwargs["ephemeral"] = True
        return context_kwargs



class Inu(hikari.GatewayBot):
    instance: "Inu" = None
    restart_count: int
    _client: lightbulb.GatewayEnabledClient | None
    
    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance
    
    def __init__(self, *args, **kwargs):
        if getattr(self, "_initialized", False):
            return  # Prevent reinitialization
        self._initialized = True
        
        self.print_banner_()
        logging.setLoggerClass(LoggingHandler)
        self.conf: ConfigProxy = ConfigProxy(
            config_type=ConfigType.YAML
        )
        self.log = getLogger(__name__, self.__class__.__name__)
        (logging.getLogger("py.warnings")).setLevel(logging.ERROR)
        self._me: Optional[hikari.User] = None
        self.startup = datetime.datetime.now()

        from core.db import Database
        self.db = Database()
        self.db.bot = self
        
        self.restart_count = 0
        self.scheduler = AsyncIOScheduler()
        self._default_prefix = self.conf.bot.DEFAULT_PREFIX  # type: ignore[attr-defined]
        self.search = Search(self)
        self.shortcuts: "Shortcuts" = Shortcuts(bot=self)
        self.id_creator = IDCreator()
        self._lavalink: Optional[lavalink_rs.LavalinkClient] = None
        self._client = None
        self.data = Data()
        

        
        logger_names = [
            "hikari", "hikari.event_manager", "ligthbulb.app", "lightbulb",
            "hikari.gateway", "hikari.ratelimits", "hikari.rest", "lightbulb.internal"
        ]
        loggers = {name: {"level": getLevel(name)} for name in logger_names}
        logs = {
            "version": 1,
            "incremental": True,
            "loggers": loggers 
        }

        super().__init__(
            self.conf.bot.DISCORD_TOKEN,
            *args,
            intents=hikari.Intents.ALL,
            logs="TRACE",
        )
        self.mrest = MaybeRest(self)
        # self.load("inu/ext/commands/")
        # self.load("inu/ext/tasks/")

        self.wait_for = self.wait_for

    # async def start(self, *args, **kwargs):
    #     await self.init_db()
        #await super().start(**kwargs)
    
    @property
    def client(self) -> lightbulb.GatewayEnabledClient:
        if not self._client:
            raise RuntimeError("Lightbulb Client is not initialized")
        return self._client

    @client.setter
    def client(self, value: lightbulb.GatewayEnabledClient) -> None:
        self._client = value
        
    @property
    def lavalink(self) -> lavalink_rs.LavalinkClient:
        if not self._lavalink:
            raise RuntimeError("Lavalink client is not initialized")
        return self._lavalink

    @lavalink.setter
    def lavalink(self, value: lavalink_rs.LavalinkClient) -> None:
        self._lavalink = value

    @property
    def accent_color(self) -> hikari.Color:
        """
        The accent color defined in the config (`bot.color`)
        """
        return hikari.Color.from_hex_code(self.conf.bot.color)

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if not (loop := asyncio.get_running_loop()):
            raise RuntimeError("Eventloop could not be returned")
        return loop

    @property
    def me(self) -> hikari.User:
        if self._me:
            return self._me
        if not (user := self.cache.get_me()):
            raise RuntimeError("Own user can't be accessed from cache")
        return user

    @property
    def user(self) -> hikari.User:
        return self.me

    @property
    def color(self) -> hikari.Color:
        """
        `self.conf.bot.color` as hikari.Color
        """
        color = self.conf.bot.color
        hex_ = cnames.get(str(color), None)
        if not isinstance(hex_, str):
            raise RuntimeError(f"matplatlib cnames has no color with name: {color}")
        return hikari.Color.from_hex_code(str(hex_))


    async def load_tasks_and_commands(self):
        await self._load("inu/ext/commands/")
        #await self._load("inu/ext/tasks/")

    async def _load(self, folder_path: str):
        """
        Loads extensions in <folder_path> and ignores files starting with `_` and ending with `.py`
        """
        # TODO: remove when finished with testing
        def is_allowed(extension: str) -> bool:
            for allowed in ALLOWED_EXTENSIONS:
                if allowed in extension:
                    return True
            return False

        self.scheduler.start()  # TODO: this should go somewhere else
        modules: Dict[str, bool] = defaultdict(lambda: True)
        for extension in os.listdir(os.path.join(os.getcwd(), folder_path)):
            if (
                extension == "__init__.py" 
                or not extension.endswith(".py")
                or extension.startswith("_")
            ):
                continue
            try:
                trimmed_name = f"{folder_path.replace('/', '.')[4:]}{extension[:-3]}"
                modules[trimmed_name]
                if not is_allowed(trimmed_name):
                    modules[trimmed_name] = False
                    continue
                importlib.import_module(trimmed_name)
                await self.client.load_extensions(trimmed_name)
            except Exception:
                self.log.critical(f"can't load {extension}\n{traceback.format_exc()}", exc_info=True)
        table = tabulate.tabulate(modules.items(), headers=["Extension", "Loaded"])
        self.log.info(table, multiline=True, prefix="init")

    async def init_db(self):
        await self.db.connect()

    def print_banner_(self):
        path = f"{os.getcwd()}/inu/data/text/banner.txt"
        with open(path, "r", encoding="utf-8") as f:
            print(f"{Fore.BLUE}{Style.BRIGHT}{f.read()}")

    async def wait_for_interaction(
        self, 
        custom_id: Optional[str] = None,
        custom_ids: List[str] | None = None,
        user_ids: Optional[int] | Optional[List[int]] = None, 
        channel_id: Optional[int] = None,
        message_id: Optional[int] = None,
        interaction_instance: Type[hikari.PartialInteraction] = hikari.ComponentInteraction,
        timeout: int | None = None,
    ) -> Tuple[str | None, InteractionCreateEvent | None, ComponentInteraction | None]:
        """
        Returns:
        str:
            first value if there is one, otherwise custom_id
            None if timeout
        InteractionCreateEvent:
            the event of the awaited interaction
            None if timeout
        ComponentInteraction:
            the component interaction to respond, of the awaited interaction
            None if timeout
        """
        if isinstance(user_ids, int):
            user_ids = [user_ids]
        try:
            event = await self.wait_for(
                InteractionCreateEvent,
                timeout=timeout or 15*60,
                predicate=lambda e:(
                    isinstance(e.interaction, interaction_instance)
                    and (True if not custom_id else custom_id == e.interaction.custom_id)     # type: ignore
                    and (True if not user_ids else e.interaction.user.id in user_ids)         # type: ignore
                    and (True if not channel_id else e.interaction.channel_id == channel_id)  # type: ignore
                    and (True if not message_id else e.interaction.message.id == message_id)  # type: ignore
                    and (True if not custom_ids else e.interaction.custom_id in custom_ids)   # type: ignore
                )
            )
            if not isinstance(event.interaction, ComponentInteraction):
                return None, None, None
            if len(event.interaction.values) > 0:
                return event.interaction.values[0], event, event.interaction
            else:
                return event.interaction.custom_id, event, event.interaction
        except asyncio.TimeoutError:
            return None, None, None
    
    async def wait_for_message(
        self,
        timeout: int = 60,
        channel_id: int | None = None,
        user_id: Optional[Snowflakeish] = None,
        interaction: Optional[ComponentInteraction] = None,
        response_type: hikari.ResponseType = hikari.ResponseType.MESSAGE_CREATE,
    ) -> Tuple[Optional[str], Optional[hikari.MessageCreateEvent]]:
        """
        Shortcut for wait_for MessageCreateEvent

        Returns:
        --------
            - (str | None) the content of the answer or None
        
        """
        return await self.ask(
            question=None,
            timeout=timeout,
            channel_id=channel_id,
            user_id=user_id,
            interaction=interaction,
            response_type=response_type,
            embed=None,
        )

    async def ask(
        self,
        question: str | None = None,
        *,
        timeout: int = 60,
        channel_id: int | None = None,
        user_id: Optional[Snowflakeish] = None,
        interaction: Optional[ComponentInteraction] = None,
        response_type: hikari.ResponseType = hikari.ResponseType.MESSAGE_CREATE,
        embed: Optional[hikari.Embed] = None
    ) -> Tuple[Optional[str], Optional[hikari.MessageCreateEvent]]:
        """
        Shortcut for wait_for MessageCreateEvent

        Args:
        ----
            - question (`str` | `None`) A string, which the bot should send, before waiting
            - timeout (`int` | `None`) The amount of time in seconds, the bot should wait for an answer
            - user_id (`int` | `None`) The user_id which the message, which the bot will wait for, should have
            - channel_id (`int`, `None`) The channel_id which the message, which the bot will wait for, should have
            - interaction (`int` | `None`) Will be used, for inital response of <`ask`> and for the channel_id
            - response_type (`hikari.ResponseType`) The response type, which will be used to ask <`ask`>
            - embed (`hiarki.Embed` | `None`) alternative to <`ask`> but which an embed, not string

        Returns:
        --------
            - (str | None) the content of the answer or None
        
        """
        if interaction and not channel_id:
            channel_id = interaction.channel_id
        if interaction and (question or embed):
            msg = await interaction.create_initial_response(response_type, question)
        elif question or embed:
            await self.rest.create_message(channel_id, question)
            msg = None
        else:
            msg = None
        try:
            event = await self.wait_for(
                hikari.MessageCreateEvent,
                timeout=timeout,
                predicate=lambda e:(
                    (True if not channel_id or not msg else e.channel_id == msg.channel_id)
                    and (True if not user_id else e.author_id == user_id)
                    and (True if not channel_id else channel_id == e.channel_id)
                )
            )
            return event.message.content, event 
        except asyncio.TimeoutError:
            return None, None



class Data:
    """Global data shared across the entire bot, used to store dashboard values."""

    def __init__(self) -> None:
        self.lavalink: LavalinkClient = None  # type: ignore
        self.preffered_music_search: Dict[int, str] = {}

class Configuration():
    """Wrapper for the config file"""
    def __init__(self, config: Mapping[str, Union[str, None]]):
        self.config = config

    def __getattr__(self, name: str) -> str:
        result = self.config[name]
        if result is None:
            raise AttributeError(f"`Configuration` file `config.yaml` has no attribute `{name}`")
        return result
    
    def __setattr__(self, name: str, value: Any) -> None:
        self.config[name] = value


class MaybeRest:
    def __init__(self, bot: Inu):
        self.bot = bot

    async def fetch_T(self, cache_method: Callable[[], Optional[T]], rest_coro: Callable[..., Coroutine[Any, Any, T]], t_ids: List[Snowflakeish]) -> T:
        t = cache_method(*t_ids)
        if t:
            return t
        return await rest_coro(*t_ids)
#typing.Callable[[params go here], typing.Awaitable[return value goes here]]
    async def fetch_user(self, user_id) -> Optional[hikari.User]:
        return await self.fetch_T(
            cache_method=self.bot.cache.get_user,
            rest_coro= self.bot.rest.fetch_user,
            t_ids=[user_id],
        )

    async def fetch_member(self, guild_id: int, member_id: int) -> Optional[hikari.Member]:
        return await self.fetch_T(
            cache_method=self.bot.cache.get_member,
            rest_coro=self.bot.rest.fetch_member,
            t_ids=[guild_id, member_id],
        )

    async def fetch_members(self, guild_id: int) -> Optional[Iterable[hikari.Member]]:
        members = await self.fetch_T(
            cache_method=self.bot.cache.get_members_view_for_guild,
            rest_coro= self.bot.rest.fetch_members,
            t_ids=[guild_id],
        )
        if isinstance(members, Mapping):
            return list(members.values())
        else:
            return members


    async def fetch_guilds(self) -> Iterable[hikari.Guild]:

        guilds = await self.fetch_T(
            cache_method=self.bot.cache.get_available_guilds_view,
            rest_coro= self.bot.rest.fetch_my_guilds,
            t_ids=[],
        )
        if isinstance(guilds, Mapping):
            return list(guilds.values())
        else:
            return guilds


    async def fetch_roles(self, member: hikari.Member) -> List[hikari.Role]:

        return await self.fetch_T(
            cache_method=member.get_roles,
            rest_coro= member.fetch_roles,
            t_ids=[],
        )


class Search:
    bot: Inu

    def __init__(self, bot: Inu):
        self.__class__.bot = bot

    @classmethod
    async def member(cls, guild_id: int, member_query: str) -> List[hikari.Member]:
        member_query = member_query.strip().lower()
        members = await cls.bot.mrest.fetch_members(guild_id)
        return [
            m for m in members 
            if (
                member_query in str(m.id).lower() 
                or member_query in str(m.username).lower()
                or member_query in m.display_name.lower()
            )
        ]

    async def guild(cls, guild_query: str) -> List[hikari.Guild]:
        guild_query = guild_query.lower().strip()
        guilds = cls.bot.cache.get_guilds_view()
        return [
            g for s, g in guilds.items()
            if guild_query in str(g.id).lower() or guild_query in str(g.name).lower()
        ]

class Shortcuts:
    """
    A class used as name space for different `wait_for` shortcuts
    """
    def __init__(self, bot: Inu):
        self.bot = bot
        # self.log = getLoggler(__name__, self.__class__.__name__)
  
    async def component_interaction(
        self,
        custom_id: str = "",
        custom_ids: List[str] = [],
        user_id: Optional[int] = None, 
        channel_id: Optional[int] = None,
        message_id: Optional[int] = None,
        timeout: int = 15*60,
        
    ) -> Tuple[Dict[str, Optional[str]], ComponentInteraction, InteractionCreateEvent]:
        """
        waits for a component interaction

        Args:
        ----
        custom_id : `str`
            The custom_id of the interaction
        custom_ids : `List[str]`
            The custom_ids of the interaction
        user_id : `int` | `None`
            The id of the user who invoked the interaction
        channel_id : `int` | `None`
            The id of the channel where the interaction was created
        message_id : `int` | `None`
            Optional message, to compare message id
        timeout : `int`
            The amount of time in seconds, the bot should wait for an answer
        
        Note:
        ----
        All given args will be used, to compare them against the new created Interaction

        Raise:
        ----
        asyncio.TimeoutError
            If the interaction was not created in the given time

        Returns:
        -------
        `Dict[str, Any]`
            Mapping from custom_id to value of the interaction
        `ComponentInteraction`
            The interaction
        `InteractionCreateEvent`
            The belonging event

        """
        event = await self.bot.app.wait_for(
            InteractionCreateEvent,
            timeout=timeout,
            predicate=lambda e:(
                isinstance(e.interaction, ComponentInteraction)
                and (True if not custom_id else custom_id == e.interaction.custom_id)
                and (True if not user_id else e.interaction.user.id == user_id)
                and (True if not channel_id else e.interaction.channel_id == channel_id)
                and (True if not message_id else e.interaction.message.id == message_id)
                and (True if not custom_ids else e.interaction.custom_id in custom_ids)
            )
        )
        if not isinstance(event.interaction, ComponentInteraction):
            raise TypeError(f"Expected `ComponentInteraction`, got `{type(event.interaction)}`")
        if len(event.interaction.values) > 0:
            return {event.interaction.custom_id: event.interaction.values[0]}, event.interaction, event
        else:
            return {event.interaction.custom_id: None}, event.interaction, event, 

    async def wait_for_modal(
        self,
        custom_id: str = "",
        custom_ids: List[str] = [],
        user_id: Optional[int] = None, 
        channel_id: Optional[int] = None,
        timeout: int = 15*60,
    ) -> Tuple[Dict[str, Any], ModalInteraction, InteractionCreateEvent]:
        """
            waits for a modal interaction

            Args:
            ----
            custom_id : `str`
                The custom_id of the interaction
            custom_ids : `List[str]`
                The custom_ids of the interaction
            user_id : `int` | `None`
                The id of the user who invoked the interaction
            channel_id : `int` | `None`
                The id of the channel where the interaction was created
            message_id : `int` | `None`
                Optional message, to compare message id
            timeout : `int`
                The amount of time in seconds, the bot should wait for an answer
            
            Note:
            ----
            All given args will be used, to compare them against the new created Interaction

            Raise:
            ----
            asyncio.TimeoutError
                If the interaction was not created in the given time

            Returns:
            -------
            `Dict[str, Any]`
                Mapping from custom_id to value of the interaction
            `ModalInteraction`
                The interaction
            `InteractionCreateEvent`
                The belonging event
            """
        event = await self.bot.wait_for(
            InteractionCreateEvent,
            timeout=timeout,
            predicate=lambda e:(
                isinstance(e.interaction, ModalInteraction)
                and (True if not custom_id else custom_id == e.interaction.custom_id)
                and (True if not user_id else e.interaction.user.id == user_id)
                and (True if not channel_id else e.interaction.channel_id == channel_id)
                and (True if not custom_ids else e.interaction.custom_id in custom_ids)
            )
        )
        if not isinstance(event.interaction, ModalInteraction):
            raise ValueError(f"Expeced ModalInteraction, got {type(event.interaction)}")
        text_inputs = {
            component.custom_id: component.value  # type: ignore
            for action_row in event.interaction.components
            for component in action_row.components
        }
        return text_inputs, event.interaction, event

    async def ask_with_modal(
        self,
        modal_title:str,
        question_s: T_STR_LIST,
        interaction: Union[hikari.ComponentInteraction, hikari.CommandInteraction],
        input_style_s: Union[TextInputStyle, List[Union[TextInputStyle, None]]] = TextInputStyle.PARAGRAPH,
        placeholder_s: Optional[Union[str, List[Union[str, None]]]] = None,
        max_length_s: Optional[Union[int, List[Union[int, None]]]] = None,
        min_length_s: Optional[Union[int, List[Union[int, None]]]] = None,
        pre_value_s: Optional[Union[str, List[Union[str, None]]]] = None,
        is_required_s: Optional[Union[bool, List[Union[bool, None]]]] = None,
        components: Optional[List[ModalActionRowBuilder]] = None,
        timeout: int = 60 * 15,
    ) -> Tuple[T_STR_LIST, ModalInteraction, InteractionCreateEvent]:
        """
        Asks a question with a modal

        Args:
        ----
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
        -------
        `List[str] | str`
            return type is given type;
            The answers of the user to the questions in the same order
        `ModalInteraction`
            The interaction
        `InteractionCreateEvent`
            The belonging event

        Raise:
        ----
        asyncio.TimeoutError
            If the interaction was not created in the given time
        ValueError
            if too many or too less arguments are given
        """
        T = TypeVar("T")
        def get_index_or_last(index: int, list_: List[T]) -> T:
            if index >= len(list_):
                return list_[-1]
            return list_[index]

        orig_questions = question_s
        questions: List[str] = []
        if isinstance(question_s, str):
            questions = [question_s]
        else:
            questions = question_s
        if isinstance(min_length_s, int):
            min_length_s = [min_length_s]
        if isinstance(max_length_s, int):
            max_length_s = [max_length_s]
        if isinstance(placeholder_s, str):
            placeholder_s = [placeholder_s]
        if isinstance(input_style_s, TextInputStyle):
            input_style_s = [input_style_s]
        if isinstance(pre_value_s, str):
            pre_value_s = [pre_value_s]
        if isinstance(is_required_s, bool):
            is_required_s = [is_required_s]
        if not components:
            components = []
            for i, question in enumerate(questions):
                modal = TextInputBuilder(custom_id=f"modal_answer-{i}", label=question)
                

                # adds corresponding items to the modal
                if max_length_s and (max_length := get_index_or_last(i, max_length_s)):
                    modal.set_max_length(max_length)
                if min_length_s and (min_length := get_index_or_last(i, min_length_s)):
                    modal.set_min_length(min_length)
                if placeholder_s and (placeholder := get_index_or_last(i, placeholder_s)):
                    modal.set_placeholder(placeholder)
                if pre_value_s and (pre_value := get_index_or_last(i, pre_value_s)):
                    modal.set_value(pre_value)
                if is_required_s and (is_required := get_index_or_last(i, is_required_s)):
                    modal.set_required(is_required)
                if input_style_s and (input_style := get_index_or_last(i, input_style_s)):
                    modal.set_style(input_style)

                # add modal part to the components
                components.append(ModalActionRowBuilder(components=[modal]))
            
        custom_id = self.bot.id_creator.create_id()
        await interaction.create_modal_response(modal_title, custom_id, components=components)
        answer_dict, modal_interaction, event = await self.wait_for_modal(custom_id=custom_id, timeout=timeout)
        if isinstance(orig_questions, str):
            return answer_dict["modal_answer-0"], modal_interaction, event
        else:
            return [value for _, value in answer_dict.items()], modal_interaction, event


class IDCreator:
    _id_count = 0

    @classmethod
    def create_id(cls) -> str:
        cls._id_count += 1
        return str(cls._id_count)