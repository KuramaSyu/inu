from datetime import datetime, timedelta
from typing import Dict, List, Tuple

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
        time_needed: timedelta,
    ) -> bool:
        """
        inserts highscore if higher then previous

        Returns:
        -------
        `bool` : 
            wehter or not highscore was inserted
        """
        table = Table("math_scores", debug_log=True)
        await table.insert(
            ["guild_id", "user_id", "stage", "highscore", "date", "time_needed"],
            values=[guild_id, user_id, stage, highscore, datetime.now(), time_needed], 
        )
        return True

    @classmethod
    async def fetch_highscores(
            cls,
            type_: str,
            guild_id: int,
            user_id: int,
        ) -> Dict[str, List[Tuple[int, int, timedelta]]]:
            """
            Fetches highscores based on the given type, guild ID, and user ID.

            Args:
            -----
            type_ : str
                The type of highscores to fetch. Valid values are "user" or "guild".
            guild_id : int
                The ID of the guild.
            user_id : int
                The ID of the user.

            Returns:
            --------
            Dict[str, List[Tuple[int, int, timedelta]]]
                A dictionary mapping from stage to a list of tuples containing user ID, highscore, and time per task.

            Raises:
            ------
            RuntimeError:
                If an invalid type is provided.

            """
            table = Table("math_scores")
            if type_ == "user":
                records = await table.select(
                    ["guild_id", "user_id"],
                    [guild_id, user_id],
                    select="*, time_needed / highscore as time_per_task",
                    order_by="highscore DESC",
                )
            elif type_ == "guild":
                records = await table.select(
                    ["guild_id"],
                    [guild_id],
                    select="*, time_needed / highscore as time_per_task",
                    order_by="highscore DESC",
                )
            else:
                raise RuntimeError(f"{type_=} is invalid")
            # mapping from stage to highscore list containing user_id, highscore and time_per_task
            stages: Dict[str, List[Tuple[int, int, float]]] = {}
            for r in records:
                stage = r["stage"]
                stage_list = stages.get(stage, [])
                stage_list.append((r["user_id"], r["highscore"], r["time_per_task"]))
                stages[stage] = stage_list
            return stages
        