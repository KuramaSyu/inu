from typing import *

import hikari

from utils import Colors
from core import Table

class SettingsManager:

    @classmethod
    async def update_activity_tracking(cls, guild_id: int, enable: bool) -> None:
        table = Table("guilds")
        await table.upsert(
            which_columns=["guild_id", "activity_tracking"],
            values=[guild_id, enable]
        )

    @classmethod
    async def fetch_activity_tracking(cls, guild_id: int) -> bool:
        """Wether or not activity logging is enabled for <guild_id>"""
        table = Table("guilds")
        records = await table.select(
            select="activity_tracking",
            columns=["guild_id"],
            matching_values=[guild_id]
        )
        try:
            return records[0]["activity_tracking"]
        except IndexError:
            # insert guild and return False
            await cls.update_activity_tracking(guild_id, False)
            return False

    @classmethod
    async def fetch_activity_tracking_all(cls) -> Dict[int, bool]:
        """
        Returns:
        -------
        Dict[int, bool] :
            Mapping from guild_id to activity_tracking bool Dict[guild_id, is_activity_tracking_enabled]
        """
        table = Table("guilds")
        records = table.fetch(f"SELECT guild_id, activity_tracking FROM {table.name}")
        mappings = {r["guild_id"]: r["activity_tracking"] for r in records}
        return mappings