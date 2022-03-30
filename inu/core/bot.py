import asyncio
import datetime
from email.message import Message
from optparse import Option
import os
import traceback
import typing
from typing import *
import logging
from asyncpraw.config import Config
from hikari.events.interaction_events import InteractionCreateEvent
from hikari.interactions.component_interactions import ComponentInteraction


import lightbulb
from lightbulb import context, commands, when_mentioned_or
import hikari
from hikari.snowflakes import Snowflakeish
from dotenv import dotenv_values
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from colorama import Fore, Style
from lightbulb.context.base import Context
from matplotlib.colors import cnames


from ._logging import LoggingHandler, getLogger, getLevel
from . import ConfigProxy, ConfigType


class BotResponseError(Exception):
    def __init__(self, bot_message: str, *args: object) -> None:
        self.bot_message = bot_message
        super().__init__(*args)


class Inu(lightbulb.BotApp):
    def __init__(self, *args, **kwargs):
        self.print_banner_()
        logging.setLoggerClass(LoggingHandler)
        self.conf: ConfigProxy = ConfigProxy(ConfigType.YAML)  #Configuration(dotenv_values())
        self.log = getLogger(__name__, self.__class__.__name__)
        (logging.getLogger("py.warnings")).setLevel(logging.ERROR)
        self._me: Optional[hikari.User] = None
        self.startup = datetime.datetime.now()
        from core.db import Database
        self.db = Database()
        self.db.bot = self
        self.log.debug(self)
        self.data = Data()
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        self._prefixes = {}
        self._default_prefix = self.conf.bot.DEFAULT_PREFIX
        self.search = Search(self)

        
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
        for log_name in ["hikari.rest", "hikari.ratelimits", "hikari.models"]:
            pass

        def get_prefix(bot: Inu, message: hikari.Message):
            return bot.prefixes_from(message.guild_id)

        super().__init__(
            *args, 
            prefix=when_mentioned_or(get_prefix), 
            token=self.conf.bot.DISCORD_TOKEN, 
            **kwargs,
            case_insensitive_prefix_commands=True,
            banner=None,
            logs=logs,
            default_enabled_guilds=[538398443006066728]
        )
        self.mrest = MaybeRest(self)
        self.load("inu/ext/commands/")
        self.load("inu/ext/tasks/")

    def prefixes_from(self, guild_id: Optional[int]) -> List[str]:
        if not guild_id:
            return [self._default_prefix, ""]
        prefixes = self._prefixes.get(guild_id, None)
        if not prefixes:
            # insert guild into table
            from core.db import Table
            table = Table("guilds")
            asyncio.create_task(table.insert(["guild_id", "prefixes"], [guild_id, [self._default_prefix]]))
        return prefixes or [self._default_prefix]

    def add_task(
        self,
        func: Callable,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        days: int = 0,
        weeks: int = 0,
        args: Sequence[Any] = None,
        kwargs: Sequence[Any] = None,
    ):
        trigger = IntervalTrigger(
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            days=days,
            weeks=weeks,
        )
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        self.scheduler.add_job(func, trigger, args=args, kwargs=kwargs)

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
        color = self.conf.bot.color
        hex_ = cnames.get(str(color), None)
        if not isinstance(hex_, str):
            raise RuntimeError(f"matplatlib cnames has no color with name: {color}")
        return hikari.Color.from_hex_code(str(hex_))


    def load_slash(self):
        for extension in os.listdir(os.path.join(os.getcwd(), "inu/ext/slash")):
            if extension == "__init__.py" or not extension.endswith(".py"):
                continue
            try:
                self.load_extensions(f"ext.slash.{extension[:-3]}")
            except Exception as e:
                self.log.critical(f"slash command {extension} can't load", exc_info=True)

    def load(self, folder_path: str):
        for extension in os.listdir(os.path.join(os.getcwd(), folder_path)):
            if (
                extension == "__init__.py" 
                or not extension.endswith(".py")
                or extension.startswith("_")
            ):
                continue
            try:
                self.load_extensions(f"{folder_path.replace('/', '.')[4:]}{extension[:-3]}")
                # self.log.debug(f"loaded plugin: {extension}")
            except Exception:
                self.log.critical(f"can't load {extension}\n{traceback.format_exc()}", exc_info=True)

    def load_task(self):
        for extension in os.listdir(os.path.join(os.getcwd(), "inu/ext/tasks")):
            if (
                extension == "__init__.py" 
                or not extension.endswith(".py")
                or extension.startswith("_")
            ):
                continue
            try:
                self.load_extensions(f"ext.tasks.{extension[:-3]}")
                self.log.debug(f"loaded plugin: {extension}")
            except Exception as e:
                self.log.critical(f"can't load {extension}\n{traceback.format_exc()}", exc_info=True)

    async def init_db(self):
        await self.db.connect()

    def print_banner_(self):
        path = f"{os.getcwd()}/inu/data/text/banner.txt"
        with open(path, "r", encoding="utf-8") as f:
            print(f"{Fore.BLUE}{Style.BRIGHT}{f.read()}")

    async def wait_for_interaction(
        self, 
        custom_id: str = "",
        custom_ids: List[str] = [],
        user_id: Optional[int] = None, 
        channel_id: Optional[int] = None,
        message_id: Optional[int] = None,
    ) -> Tuple[str, InteractionCreateEvent, ComponentInteraction]:
        try:
            self.log.debug(self)
            event = await self.wait_for(
                InteractionCreateEvent,
                timeout=10*60,
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
        channel_id: int = None,
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
        question: str = None,
        *,
        timeout: int = 60,
        channel_id: int = None,
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

        

    #override
    def run(self):
        super().run()

class Data:
    """Global data shared across the entire bot, used to store dashboard values."""

    def __init__(self) -> None:
        self.lavalink: lavasnek_rs.Lavalink = None  # type: ignore

class Configuration():
    """Wrapper for the config file"""
    def __init__(self, config: Mapping[str, Union[str, None]]):
        self.config = config

    def __getattr__(self, name: str) -> str:
        result = self.config[name]
        if result == None:
            raise AttributeError(f"`Configuration` (.env in root dir) has no attribute `{name}`")
        return result


class MaybeRest:
    def __init__(self, bot: lightbulb.BotApp):
        self.bot = bot

    async def fetch_T(self, cache_method: "function", rest_coro: Any , t_ids: List[Snowflakeish]):
        t = cache_method(*t_ids)
        if t:
            return t
        return await rest_coro(*t_ids)

    async def fetch_user(self, user_id) -> Optional[hikari.User]:
        return await self.fetch_T(
            cache_method=self.bot.cache.get_user,
            rest_coro= self.bot.rest.fetch_user,
            t_ids=[user_id],
        )

    async def fetch_member(self, guild_id: int, member_id: int) -> Optional[hikari.Member]:
        return await self.fetch_T(
            cache_method=self.bot.cache.get_member,
            rest_coro= self.bot.rest.fetch_member,
            t_ids=[guild_id, member_id],
        )

class Search:
    bot: Inu

    def __init__(self, bot: Inu):
        self.__class__.bot = bot

    async def member(cls, guild_id: int, member_query: str) -> List[hikari.Member]:
        member_query = member_query.strip().lower()
        members = await cls.bot.rest.fetch_members(guild_id)
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
        guilds = await cls.bot.rest.fetch_my_guilds()
        return [
            g for g in guilds 
            if guild_query in str(g.id).lower() or guild_query in str(g.name).lower()
        ]