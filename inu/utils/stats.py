from typing import *
import json
import typing as t
import logging

from core.db import Database

from core import getLogger

log = getLogger(__name__)

T = t.TypeVar("T")

class InvokationStats:
    db: Database
    
    def __init__(self, key: Optional[str] = None):
        self.key = key

    @classmethod
    def set_db(cls, database: Database):
        cls.db = database

    @classmethod
    def bare_bone_json(
        cls,
        command_names: Union[List[str], str] = [],
        guild_id: t.Optional[str] = None,
    ) -> str:
        if isinstance(command_names, str):
            command_names = [command_names]
        bare_bone = {
                "new": True,
        }
        for command_name in command_names:
            bare_bone[command_name] = 0
        return json.dumps(bare_bone)
    
    @classmethod
    def manipulate_json_value(
        cls,
        json_: T,
        command_name: str,
        value: int,
        is_json_str: bool = True,

    ) -> T:
        """
        adds <value> to <command_name> in <json_>
        
        NOTE:
        - <json_> can be str and dict
        - return type will be same like type of <json_>
        """
        if is_json_str:
            json_ = json.loads(json_)
        try:
            json_[command_name] += value
        except:
            json_[command_name] = value
        if is_json_str:
            return json.dumps(json_)
        else:
            return json_

    @classmethod
    async def update_json(cls, json_: str, guild_id: Optional[int]) -> None:
        """
        NOTE:
            - if guild_id = None: guild_id will be -1 interal which represents all private chats
        """
        json_ = json.loads(json_)
        is_new = json_.get("new", False)
        if guild_id is None:
            guild_id = -1
        if is_new:
            del json_["new"]
            sql = """
            INSERT INTO stats (cmd_json, guild_id)
            VALUES ($1, $2)
            """
        else:
            if guild_id:
                sql = """
                UPDATE stats
                SET cmd_json = $1
                WHERE guild_id = $2
                """
        await cls.db.execute(sql, json.dumps(json_), guild_id)

    @classmethod
    async def add_or_sub(
        cls,
        command_name: str,
        guild_id: int = None,
        value: int = 1,
    ):
        """
        Adds the value of <value> to the command <command_name> from the specific guild with id <guild_id>

        Args:
        -----
            - command_name: (str) the name of the command, where <value> should be added
            - guild_id: (int) the id of the guild
            - value: (int, default=1) the value which should be added to <command_name> for guild with id <guild_id>
        """
        sql = """
        SELECT * FROM stats
        WHERE guild_id = $1
        """
        if guild_id is None:
            guild_id = -1
        record = await cls.db.row(sql, guild_id)
        if record:
            json_ = record["cmd_json"]
        else:
            json_ = cls.bare_bone_json(command_name, guild_id)
        json_ = cls.manipulate_json_value(json_, command_name, value)
        await cls.update_json(json_, guild_id)

    @classmethod
    async def fetch_json(cls, guild_id: Optional[int]) -> Optional[Dict]:
        """
        Get a json in form of a dict, with all the command infos to <guild_id>

        Args:
        -----
            - guild_id: (int | None) the id of the guild, where you want command infos from
        """
        if guild_id is None:
            guild_id = -1
        sql = """
        SELECT * FROM stats
        WHERE guild_id = $1
        """
        record = await cls.db.row(sql, guild_id)
        if record:
            return json.loads(record["cmd_json"])
        else:
            return json.loads(cls.bare_bone_json(guild_id=guild_id))

    @classmethod
    async def fetch_global_json(cls) -> Optional[Dict]:
        """
        Get a json in form of a dict, with all the command infos
        """
        records = await cls.db.fetch("SELECT * FROM stats")
        json_ = {}
        for rec in records:
            for entry, value in rec.items():
                if entry == "guild_id":
                    continue
                to_add_json = json.loads(value)
                for command, ammount in to_add_json.items():
                    json_ = cls.manipulate_json_value(json_, command, ammount, is_json_str=False)
        return json_