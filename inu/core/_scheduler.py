from typing import (
    Union
)
import typing as t
import asyncio
import builtins

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# realized that I have no idea how to implement it with a decorator without making a own
# Plugin class which can use the return value `BotTask` from the `task` decorator.
# So I decided to add tasks inside a ShardReady listener

class BotTask:
    """
    The returned object from the `task` decorator.
    
    """
    def __init__(
        self,
        function: Union[builtins.function, t.Coroutine],
        interval: int,
        name: str,
    ):
        self.callback = function
        self.interval = interval
        self.name = name


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
            pass
