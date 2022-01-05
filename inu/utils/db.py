import asyncio
import logging
import os
import typing
from typing import (
    Final,
    Optional,
    Union,
    List,
    Any,
    TYPE_CHECKING,
    Callable,
    Sequence
)
from functools import wraps

import aiofiles
import asyncpg

from utils import Singleton
from core import Inu
if TYPE_CHECKING:
    from lightbulb import Bot

__all__: Final[Sequence[str]] = ["Database"]


def acquire(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    async def wrapper(self: "Database", *args: Any, **kwargs: Any) -> Any:
        if isinstance(self, str):
            args = (self, *args)
            self = Database()
        assert self.is_connected, "Not connected."
        self.calls += 1
        cxn: asyncpg.Connection
        async with self._pool.acquire() as cxn:
            async with cxn.transaction():
                return await func(self, *args, _cxn=cxn, **kwargs)

    return wrapper


class Database(metaclass=Singleton):
    __slots__: Sequence[str] = ("bot", "_connected", "_pool", "calls", "log")
    instance = None

    def __init__(self, bot: Optional["Inu"] = None) -> None:
        #if bot is None:
            #raise RuntimeError("`Database` object need the `Bot|Inu` object when init first")
            #return
        typing.cast(Inu, bot)
        self.bot: Inu = bot #type: ignore
        self._connected = asyncio.Event()
        self.calls = 0
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)

    async def wait_until_connected(self) -> None:
        await self._connected.wait()

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    @property
    def pool(self) -> asyncpg.Pool:
        assert self.is_connected, "Not connected."
        return self._pool # normally its called ()

    async def connect(self) -> None:
        assert not self.is_connected, "Already connected."
        pool: Optional[asyncpg.Pool] = await asyncpg.create_pool(dsn=self.bot.conf.DSN)
        if not isinstance(pool, asyncpg.Pool):
            typing.cast(Inu, self.bot)
            msg = (
                f"Requsting a pool from DSN `{self.bot.conf.DSN}` is not possible. "
                f"Try to change DSN"
            )
            self.log.critical(msg)
            raise RuntimeError(msg)

            
        self._pool: asyncpg.Pool = pool
        self._connected.set()
        self.log.info("Connected/Initialized to database successfully.")
        await self.sync()
        return

    async def close(self) -> None:
        assert self.is_connected, "Not connected."
        await self._pool.close()
        self._connected.clear()
        self.log.info("Closed database connection.")

    async def sync(self) -> None:
        await self.execute_script(os.path.join(os.getcwd(), "inu/data/bot/sql/script.sql"), self.bot.conf.DEFAULT_PREFIX)
        await self.execute_many(
            "INSERT INTO guilds (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
            [(guild,) for guild in self.bot.cache.get_available_guilds_view()],
        )
        # remove guilds where the bot is no longer in
        stored = [guild_id for guild_id in await self.column("SELECT guild_id FROM guilds")]
        member_of = self.bot.cache.get_available_guilds_view()
        to_remove = [(guild_id,) for guild_id in set(stored) - set(member_of)]
        await self.execute_many("DELETE FROM guilds WHERE guild_id = $1;", to_remove)

        self.log.info("Synchronised database.")

    @acquire
    async def execute(self, query: str, *values: Any, _cxn: asyncpg.Connection) -> Optional[asyncpg.Record]:
        return await _cxn.execute(query, *values)
        

    @acquire
    async def execute_many(self, query: str, valueset: List[Any], _cxn: asyncpg.Connection) -> None:
        await _cxn.executemany(query, valueset)

    @acquire
    async def val(self, query: str, *values: Any, column: int = 0, _cxn: asyncpg.Connection) -> Any:
        """Returns a value of the first row from a given query"""
        return await _cxn.fetchval(query, *values, column=column)

    @acquire
    async def column(
        self, query: str, *values: Any, column: Union[int, str] = 0, _cxn: asyncpg.Connection
    ) -> List[Any]:
        return [record[column] for record in await _cxn.fetch(query, *values)]

    @acquire
    async def row(self, query: str, *values: Any, _cxn: asyncpg.Connection) -> Optional[List[Any]]:
        """Returns first row of query"""
        return await _cxn.fetchrow(query, *values)

    @acquire
    async def fetch(self, query: str, *values: Any, _cxn: asyncpg.Connection) -> List[asyncpg.Record]:
        """Executes and returns (if specified) a given `query`"""
        return await _cxn.fetch(query, *values)

    @acquire
    async def execute_script(self, path: str, *args: Any, _cxn: asyncpg.Connection) -> None:
        async with aiofiles.open(path, "r") as script:
            await _cxn.execute((await script.read()) % args)

######Database
#### tables
## guilds: guildid
####
## tags: id INT, tag_key - TEXT; tag_value - List[TEXT]; creator_id - INT; guild_id - INT