import asyncio
import typing
from typing import (
    Dict,
    Union,
    Optional,
    List,
)

import hikari
from hikari.events.shard_events import ShardReadyEvent
import lightbulb
from lightbulb import Plugin


class DailyPosts(Plugin):
    @lightbulb.listener(hikari.ShardReadyEvent)
    async def load_tasks(self, event: ShardReadyEvent)