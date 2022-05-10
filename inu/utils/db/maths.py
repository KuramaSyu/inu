from datetime import datetime
from typing import Dict, List

from core import Table, Database, getLogger

log = getLogger(__name__)


class MathScoreManager:

    @classmethod
    async def maybe_set_record(
        cls,
        guild_id: int,
        user_id: int,
        stage: str,
        highscore: int,
    ) -> bool:
        """
        ### inserts highscore if higher then previous

        Returns:
        -------
        `bool` : 
            wehter or not highscore was updated
        """
        table = Table("math_scores", debug_log=True)
        user_stage = await table.select_row(["guild_id", "user_id", "stage"], [guild_id, user_id, stage])
        if user_stage:
            old_highscore = user_stage["highscore"]
        else:
            old_highscore = 0
        if old_highscore < highscore:
            await table.upsert(
                ["guild_id", "user_id", "stage", "highscore", "date"],
                values=[guild_id, user_id, stage, highscore, datetime.now()],
                compound_of=3
            )
            return True
        return False

    @classmethod
    async def fetch_highscores(
        cls,
        type_: str,
        guild_id: int,
        user_id: int,
    ):
        """
        Args:
        -----
        type_ : `str` 
            the type [user|guild] (all from user or only user from guild)
        guild_id : `int`
        user_id : `int`


        Returns:
        --------
            - (`Dict[str, List[Dict[int, int]]]`) Mapping form stage to highscore list containing
              Dict mapping from user_id to highscore
              -> Dict[stage, ListSortedDown[Dict[user_id, highscore]]]
        """
        table = Table("math_scores")
        if type_ == "user":
            records = await table.select(
                ["guild_id", "user_id"],
                [guild_id, user_id],
                order_by="highscore DESC",
            )
        elif type_ == "guild":
            records = await table.select(
                ["guild_id"],
                [guild_id],
                order_by="highscore DESC",
            )
        else:
            raise RuntimeError(f"{type_=} is unvalid")
        stages: Dict[str, List[Dict[int, int]]] = {}
        for r in records:
            stage = r["stage"]
            stage_list = stages.get(stage, [])
            stage_list.append({r["user_id"]: r["highscore"]})
            stages[stage] = stage_list
        return stages
        