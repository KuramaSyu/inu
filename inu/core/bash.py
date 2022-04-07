import asyncio
from typing import *
import traceback

from ._logging import getLogger
log = getLogger(__name__)


class Bash:
    @classmethod
    async def execute(cls, query: List[str]) -> Tuple[str, str]:
        """
        Executes a bash command
        Parameters:
        query: The bash command to execute
        Returns:
        stdout: The stdout of the command
        stderr: The stderr of the command
        """
        proc = await asyncio.create_subprocess_exec(
            *query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()
        if stderr:
            log.error(stderr.decode())
        return stdout.decode("utf-8"), stderr.decode("utf-8")

    @classmethod
    async def qalc(cls, query: str, terse: bool = True) -> str:
        """
        tries to calculate a query

        Parameters:
        -----------
        query: 
            The query to calculate

        Returns:
        --------
        str:
            The result of the calculation

        Raises:
        -------
        ValueError: 
            If the query could not be calculated (error contains stderr)
        """
        args = ["qalc"]
        #args.append(f"--base={base}")
        if terse:
            args.append("-t")
        args.append(query)
        out, err = await cls.execute(args) # "-t",
        if err:
            raise ValueError(err)
        return out
