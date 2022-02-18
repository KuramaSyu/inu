import asyncio
import random
from typing import *

import lightbulb
from lightbulb import commands
from lightbulb.context import Context
import hikari
from hikari import Embed

from utils import NumericStringParser, Multiple


class Calculation:
    def __init__(
        self,
        max_number: int,
        operations: int,
        allowed_endings: List[str] = [".0"],
        allowed_symbols: List[str] = ["*", "/", "+", "-"],
        allowed_partial_endings: List[str] = [".1", ".2", "0.5"],
        
    ):
        """
        Args:
        -----
            - max_number (int) The maximum number, which will appear in the end string
            - operations (int) How many operations the calculation will have
            - allowed_endings (`List[str]`, Default = `[".0"]`) allowed endings from the result of the end string
            - allowed_symbols (`List[str]`, Default = `["*", "/", "+", "-"]`) all allowed operations for the calc string
            - allowed_partial_endings (`List[float]`, default = `0.1, 0.2, 0.5]`) allowed endings of interm results 
        """
        nsp = NumericStringParser()
        self.calc = nsp.eval
        self._allowed_endings = allowed_endings
        self._allowed_symbols = allowed_symbols
        self._allowed_partial_endings = allowed_partial_endings
        self._max_number = max_number
        # when exeeding 2000 raise error
        
    
    def get_task(self) -> str:
        try:
            return self.create_calculation_task
        except RuntimeError:
            return self.get_task()

    def create_calculation_task(self) -> str:
        creation_trys = 0
        calc_str = str(self.get_rnd_number())
        op = self.get_rnd_symbol()
        num = self.get_rnd_number()
        for x in range(self.operations):
            if x != self.operations:
                while not self.is_allowed(f"{calc_str}{op}{num}"):
                    op = self.get_rnd_symbol()
                    num = self.get_rnd_number()
                    creation_trys += 1
                    if creation_trys > 2000:
                        raise RuntimeError(f"Creation not possible with string: {calc_str}{op}{num}")
            else:
                op = self.get_rnd_symbol()
                num = self.get_rnd_number()
                while not self.is_allowed(f"{calc_str}{op}{num}"):
                    op = self.get_rnd_symbol()
                    num = self.get_rnd_number()
                calc_str = f"{calc_str}{op}{num}"
        return calc_str

    def get_rnd_number(self) -> int:
        random.randrange(1, self.max_number + 1)

    def get_rnd_symbol(self):
        return random.choice(self._allowed_symbols)

    def is_allowed(self, calc: str, end: bool = False) -> bool:
        result = str(self.calc(calc))
        if end:
            return Multiple.endswith_(result, self._allowed_endings)
        else:
            return Multiple.endswith_(result, self._allowed_partial_endings)
        





plugin = lightbulb.Plugin("mind_training", "Contains calcualtion commands")

@plugin.command
@lightbulb.command("mind-training", "Menu with all calculation tasks I have")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def calculation_tasks(ctx: Context):
    embed = Embed(title="Calculations")