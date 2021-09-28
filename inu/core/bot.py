import asyncio
from distutils.debug import DEBUG
import os
import traceback
import typing
from typing import (
    Mapping,
    Union,
    Optional
)
import logging
from utils.logging import LoggingHandler

logging.setLoggerClass(LoggingHandler)


import lightbulb
import hikari
from dotenv import dotenv_values


class Inu(lightbulb.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)
        self.load_prefix()
        self.load_slash()
        self.conf: Configuration = Configuration(dotenv_values())
        self._me: Optional[hikari.User] = None
        from utils.db import Database
        self.db = Database(self)


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

    def load_slash(self):
        for extension in os.listdir(os.path.join(os.getcwd(), "inu/ext/slash")):
            if extension == "__init__.py" or not extension.endswith(".py"):
                continue
            try:
                self.load_extension(f"ext.slash.{extension[:-3]}")
            except Exception as e:
                self.log.critical(f"slash command {extension} can't load", exc_info=True)

    def load_prefix(self):
        for extension in os.listdir(os.path.join(os.getcwd(), "inu/ext/prefix")):
            if (
                extension == "__init__.py" 
                or not extension.endswith(".py")
                or extension.startswith("_")
            ):
                continue
            try:
                self.load_extension(f"ext.prefix.{extension[:-3]}")
                self.log.debug(f"loaded plugin: {extension}")
            except Exception as e:
                self.log.critical(f"can't load {extension}\n{traceback.format_exc()}", exc_info=True)

    async def init_db(self):
        await self.db.connect()


    #override
    def run(self):
        super().run()

class Configuration():
    """Wrapper for the config file"""
    def __init__(self, config: Mapping[str, Union[str, None]]):
        self.config = config

    def __getattr__(self, name: str) -> str:
        result = self.config[name]
        if result == None:
            raise AttributeError(f"`Configuration` has no attribute `{name}`")
        return result