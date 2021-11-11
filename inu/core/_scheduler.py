from typing import (
    Union
)
import typing as t
import asyncio
import builtins

from apscheduler.schedulers.asyncio import AsyncIOScheduler


class BotTask:
    def __init__(
        self,
        function: Union[builtins.function, t.Coroutine],
        interval: int,
        name: str,
    ):
    self.callback = function


def task(interval: int):
    """
    Decorator to add a task (function with interval) to the bot.

    Args:
    -----
        - interval: (int) the interval in seconds the decorated function should have
    """
    def decorator(func: Union[t.Coroutine, builtins.function]):
        name = func.__qualname__
        def wrapper(*args, **kwargs):
