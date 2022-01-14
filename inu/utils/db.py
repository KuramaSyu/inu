import asyncio
import logging
import os
import typing
from typing import *
from functools import wraps
import traceback

import aiofiles
import asyncpg

from utils import Singleton
from core import Inu
if TYPE_CHECKING:
    from lightbulb import Bot

__all__: Final[Sequence[str]] = ["Database"]

from core import getLogger

log = getLogger(__name__)

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
        self.log = getLogger(__name__, self.__class__.__name__)

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
        pool: Optional[asyncpg.Pool] = await asyncpg.create_pool(dsn=self.bot.conf.db.DSN)
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
        await self.execute_script(os.path.join(os.getcwd(), "inu/data/bot/sql/script.sql"), self.bot.conf.bot.DEFAULT_PREFIX)
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

class KeyValueDB:
    db: Database


class Table():
    def __init__(self, table_name: str, debug_log: bool = False):
        self.name = table_name
        self.db = Database()
        self.do_log = debug_log
        self._executed_sql = ""


    def logging(reraise_exc: bool = True):
        def decorator(func: "function"):
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                self = args[0]
                log = getLogger(__name__, self.name, func.__name__)
                try:
                    return_value = await func(*args, **kwargs)
                    if self.do_log:
                        log.debug(f"{return_value}")
                    return return_value
                except Exception as e:
                    log.warning(f"{self._executed_sql}")
                    log.exception(f"{traceback.format_exc()}")
                    if reraise_exc:
                        raise e
                    return None
            return wrapper
        return decorator

    @logging()
    async def insert(self, which_columns: List[str], values: List, returning: str = "*") -> Optional[asyncpg.Record]:
        values_chain = [f'${num}' for num in range(1, len(values)+1)]
        sql = (
            f"INSERT INTO {self.name} ({', '.join(which_columns)})"
            f"VALUES ({', '.join(values_chain)})"
            f"RETURNING {returning}"
        )
        log.debug(sql)
        return_values = await self.db.execute(sql, *values)
        return return_values

    @logging()
    async def upsert(self, which_columns: List[str], values: List, returning: str = "*") -> Optional[asyncpg.Record]:
        """
        NOTE
        ----
            - the first value of `which_columns` and `values` should be the id!
        """
        values_chain = [f'${num}' for num in range(1, len(values)+1)]
        update_set_query = ""
        for i, item in enumerate(zip(which_columns, values_chain)):
            if i == 0:
                continue
            update_set_query += f"{item[0]}={item[1]}, "
        update_set_query = update_set_query[:-2]  # remove last ","
        sql = (
            f"INSERT INTO {self.name} ({', '.join(which_columns)}) \n"
            f"VALUES ({', '.join(values_chain)}) \n"
            f"ON CONFLICT ({which_columns[0]}) DO UPDATE \n"
            f"SET {update_set_query}"
        )
        self._create_sql_log_message(sql, values)
        return_values = await self.db.execute(sql, *values)
        return return_values   

    @logging()
    async def delete(
        self, 
        columns: List[str], 
        matching_values: List, 
    ) -> Optional[List[Dict[str, Any]]]:
        """
        DELETE FROM table_name
        WHERE <columns>=<matching_values>
        RETURNING *
        """
        where = self.__class__.create_where_statement(columns)

        sql = (
            f"DELETE FROM {self.name}\n"
            f"WHERE {where}\n"
            f"RETURNING *"
        )
        self._create_sql_log_message(sql, matching_values)

        records = await self.db.execute(sql, *matching_values)
        return records

    @logging()
    async def alter(self):
        pass

    @logging()
    async def select(
        self, 
        columns: List[str], 
        matching_values: List, 
        order_by: Optional[str] = None, 
        select: str = "*"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        SELECT <select> FROM `this`
        WHERE <columns>=<matching_values>
        ORDER BY <order_by> (column ASC|DESC)
        """
        where = self.__class__.create_where_statement(columns)

        sql = (
            f"SELECT {select} FROM {self.name}\n"
            f"WHERE {where}"
        )
        if order_by:
            sql += f"\nORDER BY {order_by}"
        self._create_sql_log_message(sql, matching_values)

        records = await self.db.fetch(sql, *matching_values)
        return records
    
    async def select_row(self, columns: List[str], matching_values: List, select: str = "*") -> Optional[asyncpg.Record]:
        records = await self.select(columns, matching_values, select=select)
        if not records:
            return None
        return records[0]

    @logging()
    async def update(self):
        pass

    async def delete_by_id(self, column: str, value: Any) -> Optional[Dict]:
        """
        Delete a record by it's id
        """
        return await self.delete(
            columns=[column],
            matching_values=[value],
        )

    @staticmethod
    def create_where_statement(columns: List[str]) -> str:
        where = ""
        for i, item in enumerate(columns):
            where += f"{'and ' if i > 0 else ''}{item}=${i+1} "
        return where
    
    def _create_sql_log_message(self, sql:str, values: List):
        self._executed_sql = (
            f"SQL:\n"
            f"{sql}\n"
            f"WITH VALUES: {values}"
        )
