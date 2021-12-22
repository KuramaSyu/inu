from typing import *
import json
import typing as t



from .db import Database


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
        command_names: Union[List[str], str],
        guild_id: t.Optional[str],
    ) -> str:
        if isinstance(command_names, str):
            command_names = [command_names]
        bare_bone = {
                "guild_id": guild_id,
        }
        for command_name in command_names:
            bare_bone[command_name] = 0
        return json.dumps(bare_bone)
    
    @classmethod
    def manipulate_json_value(
        cls,
        json_: str,
        command_name: str,
        value: int,

    ) -> str:
        json_ = json.loads(json_)
        try:
            json_[command_name] += value
        except:
            json_[command_name] = value
        return json.dumps(json_)

    @classmethod
    async def update_json(cls, json_: str) -> None:
        json_ = json.loads(json_)
        guild_id = json_["guild_id"]
        try:
            guild_id = int(guild_id)
        except:
            pass
        sql = """
        UPDATE stats
        SET invokations = $1
        WHERE guild_id = $2
        """
        await cls.db.execute(sql, int(json_["invokations"]), guild_id)

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
        record = await cls.db.fetch(sql, guild_id)
        if record:
            json_ = json.loads(record["json"])
        else:
            json_ = cls.bare_bone_json(command_name, guild_id)
        json_ = cls.manipulate_json_value(json_, command_name, value)
        cls.update_json(json_)

    @classmethod
    async def fetch_json(cls, guild_id: Optional[int]) -> Optional[Dict]:
        """
        Get a json in form of a dict, with all the command infos to <guild_id>

        Args:
        -----
            - guild_id: (int | None) the id of the guild, where you want command infos from
        """
        sql = """
        SELECT * FROM stats
        WHERE guild_id = $1
        """
        record = await cls.db.fetch(sql, guild_id)
        if record:
            return json.loads(record["json"])
        else:
            return cls.bare_bone_json(guild_id)