from argparse import Action
import asyncio
from email.message import Message
import random
from typing import *

import lightbulb
from lightbulb import ResponseProxy, commands
from lightbulb.context import Context
import hikari
from hikari.impl import ActionRowBuilder
from hikari import Embed
from core.bot import Inu

from utils import NumericStringParser, Multiple, Colors


class CalculationBlueprint:
    def __init__(
        self,
        max_number: int,
        operations: int,
        max_time: int,
        min_number: int = 1,
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
        self._operations = operations
        self.calc = nsp.eval
        self._allowed_endings = allowed_endings
        self._allowed_symbols = allowed_symbols
        self._allowed_partial_endings = allowed_partial_endings
        self._max_number = max_number
        self._min_number = min_number
        self._max_time = max_time

        # when exeeding 2000 raise error
    @staticmethod
    def get_result(to_calc: str):
        nsp = NumericStringParser()
        return nsp.eval(to_calc)
    
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
        for x in range(self._operations):
            if x != self._operations:
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
        random.randrange(self._min_number, self.max_number + 1)

    def get_rnd_symbol(self):
        return random.choice(self._allowed_symbols)

    def is_allowed(self, calc: str, end: bool = False) -> bool:
        result = str(self.calc(calc))
        if end:
            return Multiple.endswith_(result, self._allowed_endings)
        else:
            return Multiple.endswith_(result, [*self._allowed_partial_endings, *self._allowed_endings])

    def __str__(self) -> str:
        text = ""
        text += f"Amount of operations: {self._operations}"
        text += f"Operations: {', '.join(f'`{s}`' for s in self._allowed_symbols)}\n"
        text += f"Numbers from {self._min_number} to {self._max_number}\n"
        text += f"Time: {self._max_time}s/task"
        text += f"Example: `{self.get_task()}`"
        return text


plugin = lightbulb.Plugin("mind_training", "Contains calcualtion commands")

bot: Optional[Inu] = None
stages = {
    1: CalculationBlueprint(
        max_number=9,
        operations=1,
        max_time=10,
        allowed_partial_endings=[],
        allowed_endings=[".0"],
    )
}

@plugin.command
@lightbulb.command("mind-training", "Menu with all calculation tasks I have")
@lightbulb.implements(commands.PrefixCommand)
async def calculation_tasks(ctx: Context):
    embed = Embed(title="Calculation tasks")
    menu = ActionRowBuilder().add_select_menu("calculation_task_menu")
    for i, c in stages.items():
        embed.add_field(f"Stage {i}", str(c), inline=True)
        menu.add_option(f"Stage {i}", f"{i}").add_to_menu()
    menu = menu.add_to_container()
    if bot is None:
        raise RuntimeError
    await ctx.respond(embed=embed, component=menu)
    option = await bot.wait_for_interaction("calculation_task_menu", ctx.user.id, ctx.channel_id)
    if not option:
        return
    else:
        c = stages[option]
        await execute_task(ctx, c)
    

async def _change_embed_color(msg: ResponseProxy, embed: Embed, in_seconds: int):
    await asyncio.sleep(in_seconds)
    await msg.edit(embed=embed)

async def execute_task(ctx: Context, c: CalculationBlueprint) -> int:
    """
    Returns:
    -------
        - (int) the amount of tasks, the user finished 
    """

    if bot is None:
        raise RuntimeError(f"Inu is None") # should never happen
    tasks_done = 0
    while True:
        current_task = c.get_task().replace('*', 'x')
        embed = Embed(title=f"What is {current_task} ?")
        embed.color = Colors.from_name("green")
        msg = await ctx.respond(embed=embed)
        tasks = []
        colors = ["yellow", "orange", "red"]
        for x in range(4):
            embed = Embed(title=f"What is {c.get_task().replace('*', 'x')} ?")
            embed.color = Colors.from_name(colors[x])
            when = x+1 * c._max_time / 4
            tasks.append(
                asyncio.create_task(
                    _change_embed_color(msg, embed, when)
                )
            )
        answer, event = await bot.wait_for_message(
            timeout=c._max_time,
            channel_id=ctx.channel_id,
            user_id=ctx.user,
        )
        if not answer:
            break
        try:
            if float(answer.strip) == float(c.get_result(current_task)):
                await event.message.add_reaction("✅")
            else:
                await event.message.add_reaction("❌")
        except:
            pass

        tasks_done += 1
    await ctx.respond(f"You solved {tasks_done} tasks")
    return tasks_done


def load(inu: Inu):
    inu.add_plugin(plugin)
    global bot
    bot = Inu






