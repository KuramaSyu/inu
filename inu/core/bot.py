import asyncio
import os
import typing
from typing import (
    Mapping,
    Union
)

import lightbulb
import hikari
from dotenv import dotenv_values

from utils import build_logger #type: ignore

log = build_logger(__name__)

class Inu(lightbulb.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_prefix()
        self.load_slash()
        self.conf: Mapping[str, Union[str, None]] = dotenv_values()

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if not (loop := asyncio.get_running_loop()):
            raise RuntimeError("Eventloop could not be returned")
        return loop

    @property
    def me(self) -> hikari.User:
        if not (user := self.cache.get_me()):
            raise RuntimeError("Own user can't be accessed from cache")
        return user

    @property 
    def user(self) -> hikari.User:
        return self.me

    def load_slash(self):
        for extension in os.listdir(os.path.join(os.getcwd(), "ext/slash")):
            if extension == "__init__.py" or not extension.endswith(".py"):
                continue
            try:
                self.load_extension(f"ext.slash.{extension[:-3]}")
            except Exception as e:
                log.critical(f"slash command {extension} can't load", exc_info=True)

    def load_prefix(self):
        for extension in os.listdir(os.path.join(os.getcwd(), "ext/prefix")):
            if extension == "__init__.py" or not extension.endswith(".py"):
                continue
            try:
                self.load_extension(f"ext.prefix.{extension[:-3]}")
            except Exception as e:
                log.critical(f"can't load {extension}", exc_info=True)