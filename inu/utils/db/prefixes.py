from typing import *

from core import getLogger, Table, Inu

log = getLogger(__name__)


class PrefixManager:

    @classmethod
    async def add_prefix(
        cls,
        guild_id: int,
        prefix: str,
    ) -> List[str]:
        """
        Returns:
        --------
            - (List[str]) prefixes
        """
        table = Table("guilds")
        
        rec = await table.fetch_by_id("guild_id", guild_id)
        prefixes = [table.db.bot.conf.bot.DEFAULT_PREFIX]
        if rec:
            prefixes.extend(rec["prefixes"])
        prefixes.append(prefix)
        prefixes = list(set(prefixes))
        await table.upsert(["guild_id", "prefixes"], [guild_id, prefixes])
        table.db.bot._prefixes[guild_id] = prefixes
        return prefixes

    @classmethod
    async def remove_prefix(
        cls,
        guild_id: int,
        prefix: str,
    ) -> List[str]:
        """
        Returns:
        --------
            - (List[str]) prefixes
        """
        table = Table("guilds")
        rec = await table.fetch_by_id("guild_id", guild_id)
        prefixes = []
        if rec:
            prefixes.extend(rec["prefixes"])
        try:
            prefixes.remove(prefix)
        except ValueError:
            pass
        prefixes = list(set(prefixes))
        await table.upsert(["guild_id", "prefixes"], [guild_id, prefixes])
        table.db.bot._prefixes[guild_id] = prefixes
        return prefixes