import asyncio
import logging
import os
import typing
from typing import *
from functools import wraps
import traceback

import aiofiles
import asyncpg
import pandas as pd

from core import Inu
from . import Singleton, ConfigProxy, ConfigType
if TYPE_CHECKING:

    from lightbulb import Bot

__all__: Final[Sequence[str]] = ["Database"]

from core import getLogger

log = getLogger(__name__)
conf = ConfigProxy(ConfigType.YAML)
table_logging = conf.db.SQL_logging
log.info(f"DB table DEBUG logging: {table_logging}")

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
    __slots__: Sequence[str] = ("_bot", "_connected", "_pool", "calls", "log")
    instance = None

    def __init__(self, bot: Optional["Inu"] = None) -> None:
        #if bot is None:
            #raise RuntimeError("`Database` object need the `Bot|Inu` object when init first")
            #return
        typing.cast(Inu, bot)
        self._bot: Inu #type: ignore
        self._connected = asyncio.Event()
        self.calls = 0
        self.log = getLogger(__name__, self.__class__.__name__)

    async def wait_until_connected(self) -> None:
        await self._connected.wait()

    @property
    def bot(self) -> Inu:
        assert(isinstance(self._bot, Inu))
        return self._bot
    
    @bot.setter
    def bot(self, value: Inu) -> None:
        self._bot = value
        log.info(f"set bot to: {value}")

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    @property
    def pool(self) -> asyncpg.Pool:
        assert self.is_connected, "Not connected."
        return self._pool # normally its called ()

    async def connect(self) -> None:
        assert not self.is_connected, "Already connected."
        log.debug(self.bot)
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
    do_log = None
    def __init__(self, table_name: str, debug_log: bool = table_logging):
        self.name = table_name
        self.db = Database()
        if self.do_log is None:
            self.__class__.do_log = self.db.bot.conf.db.SQL_logging
            log.info(f"set debug table logging to: {self.do_log}")
        self._executed_sql = ""
        self._as_dataframe: bool = False

    def return_as_dataframe(self, b: bool) -> None:
        self._as_dataframe = b

    def logging(reraise_exc: bool = True):
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                self = args[0]
                log = getLogger(__name__, self.name, func.__name__)
                try:
                    return_value = await func(*args, **kwargs)
                    if self.do_log:
                        log.debug(f"{self._executed_sql}\n->{return_value}")
                    return return_value
                except Exception as e:
                    log.error(f"{self._executed_sql}")
                    log.exception(f"{traceback.format_exc()}")
                    if reraise_exc:
                        raise e
                    return None
            return wrapper
        return decorator

    def formatter(func: Callable) -> Callable[["Table", Any], Callable[[Any], Awaitable]]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            self = args[0]
            return_value = await func(*args, **kwargs)
            if self._as_dataframe:
                columns = []
                if isinstance(return_value, list):
                    if len(return_value) > 0:
                        columns = [k for k in return_value[0].keys()]
                    else:
                        columns = []
                elif isinstance(return_value, dict):
                    columns = [k for k in return_value.keys()]
                else:
                    raise TypeError(f"{type(return_value)} is not supported. Only list and dict can be converted to dataframe.")
                return_value = pd.DataFrame(data=return_value, columns=columns)
            return return_value
        return wrapper


    @logging()
    async def insert(
        self, 
        which_columns: List[str], 
        values: List, 
        returning: str = "*"
    ) -> Optional[asyncpg.Record]:
        """
        insert into table <`wihich_columns`> values <`values`> returning <`returning`>

        Args:
        -----
        which_columns: `List[str]`
            the column names where you want to insert
        values: `List[Any]`
            the matching values to which_columns
        returning: `str`
            the column(s) which should be returned
        
        """
        values_chain = [f'${num}' for num in range(1, len(values)+1)]
        sql = (
            f"INSERT INTO {self.name} ({', '.join(which_columns)})\n"
            f"VALUES ({', '.join(values_chain)})\n"
            f"RETURNING {returning}\n"
        )
        self._create_sql_log_message(sql, values)
        return_values = await self.db.execute(sql, *values)
        return return_values

    @logging()
    @formatter
    async def upsert(
        self, 
        which_columns: List[str], 
        values: List,
        compound_of: int = 0,
        returning: str = ""
    ) -> Optional[asyncpg.Record]:
        """
        NOTE
        ----
            - the first value of `which_columns` and `values` should be the id!
            - if the id is a compound, then pass these first into `which_columns` and `values`
              and set `compound_of` to the number, how many values count 
              (until wich index + 1) to that compound
        """
        values_chain = [f'${num}' for num in range(1, len(values)+1)]
        update_set_query = ""
        for i, item in enumerate(zip(which_columns, values_chain)):
            if i == 0:
                continue
            update_set_query += f"{item[0]}={item[1]}, "
        update_set_query = update_set_query[:-2]  # remove last ","
        on_conflict_values = which_columns[0]
        if compound_of:
            on_conflict_values = ", ".join(c for c in which_columns[:compound_of])
        sql = (
            f"INSERT INTO {self.name} ({', '.join(which_columns)}) \n"
            f"VALUES ({', '.join(values_chain)}) \n"
            f"ON CONFLICT ({on_conflict_values}) DO UPDATE \n"
            f"SET {update_set_query} \n"
        )
        if returning:
            sql += f"RETURNING {returning} \n"
        self._create_sql_log_message(sql, values)
        return_values = await self.db.execute(sql, *values)
        return return_values   

    @logging()
    @formatter
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
    @formatter
    async def alter(self):
        pass

    @logging()
    @formatter
    async def select(
        self, 
        columns: List[str], 
        matching_values: List,
        additional_values: Optional[List] = None,
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
        if additional_values:
            matching_values.extend(additional_values)
        self._create_sql_log_message(sql, matching_values)

        records = await self.db.fetch(sql, *matching_values)
        return records

    async def select_row(self, columns: List[str], matching_values: List, select: str = "*") -> Optional[asyncpg.Record]:
        records = await self.select(columns, matching_values, select=select)
        if not records:
            return None
        return records[0]

    @logging()
    @formatter
    async def update(self):
        pass

    async def delete_by_id(self, column: str, id: Any) -> Optional[Dict]:
        """
        Delete a record by it's id
        """
        return await self.delete(
            columns=[column],
            matching_values=[id],
        )

    async def fetch_by_id(self, column: str, id: Any) -> Optional[Dict]:
        """
        Fetch a record by it's id
        """
        rec = await self.select(
            columns=[column],
            matching_values=[id],
        )
        if not rec:
            return None
        return rec[0]

    @logging()
    @formatter
    async def fetch(self, sql: str, *args) -> Optional[List[asyncpg.Record]]:
        """
        Execute custom SQL with return
        """
        self._create_sql_log_message(sql, [*args])
        return await self.db.fetch(sql, *args)

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

    async def execute(self, sql: str, *args) -> Optional[List[asyncpg.Record]]:
        """
        Execute custom SQL with return
        """
        return await self.fetch(sql, *args)
