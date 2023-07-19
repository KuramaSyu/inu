
import asyncio
from datetime import datetime, timedelta
import random
from time import time
import traceback
from typing_extensions import Self
from typing import *


import lightbulb
from lightbulb import ResponseProxy, commands
from lightbulb.context import Context
import hikari
from hikari.impl import MessageActionRowBuilder
from hikari import ButtonStyle, ComponentInteraction, Embed, ResponseType
from core.bot import Inu, getLogger
from utils.language import Human

from utils import (
    NumericStringParser,
    Multiple, 
    Colors, 
    MathScoreManager, 
    Paginator
)

log = getLogger(__name__)



class CalculationBlueprint:
    """Class to create calculations"""
    def __init__(
        self,
        max_number: int,
        operations: int,
        max_time: int,
        name: str,
        min_number: int = 1,
        allowed_endings: List[str] = [".0"],
        allowed_symbols: List[str] = ["*", "/", "+", "-"],
        allowed_partial_endings: List[str] = [".1", ".2", "0.5"],
        max_result_number: Optional[int] = None,
        display_name: str = "",

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
        # add space for optic later on
        self._allowed_symbols = [s.strip() for s in allowed_symbols]
        self._allowed_partial_endings = allowed_partial_endings
        self._max_number = max_number
        self._min_number = min_number
        self._max_time = max_time
        self.name = name
        self._max_result_number = max_result_number
        self.display_name = display_name or self.name
        

        # when exeeding 2000 raise error
    @staticmethod
    def get_result(to_calc: str):
        to_calc = to_calc.replace("x", "*").replace(":", "/")
        nsp = NumericStringParser()
        return nsp.eval(to_calc)
    
    def get_task(self) -> Tuple[str, str]:
        """
        Returns:
            - (`str`) the bare calc_str which can be calculated by class `self`
            - (`str`) the more beautifull version of the string above
        """
        try:
            return self.create_calculation_task()
        except RuntimeError:
            return self.get_task()

    def create_calculation_task(self) -> Tuple[str, str]:
        """
        Returns:
            - (`str`) the bare calc_str which can be calculated by class `self`
            - (`str`) the more beautifull version of the string above
        """
        tokens = []
        creation_trys = 0
        calc_str = str(self.get_rnd_number())
        op = self.get_rnd_symbol()
        num = self.get_rnd_number()
        tokens.append(float(calc_str))
        for x in range(self._operations):
            op = self.get_rnd_symbol()
            num = self.get_rnd_number()
            if x != self._operations:
                while not self.is_allowed(f"{calc_str}{op}{num}"):
                    op = self.get_rnd_symbol()
                    num = self.get_rnd_number()
                    creation_trys += 1
                    if creation_trys > 200:
                        raise RuntimeError(f"Creation not possible with string: {calc_str}{op}{num}")
            else:
                while not self.is_allowed(f"{calc_str}{op}{num}"):
                    op = self.get_rnd_symbol()
                    num = self.get_rnd_number()
            calc_str = f"{calc_str}{op}{num}"
            tokens.extend([op, float(num)])

        return calc_str, self.human_calc_str(tokens)
    
    @staticmethod
    def human_calc_str(tokens: List[Union[str, float]]) -> str:
        """
        Example:
        >>> human_calc_str([12, "*", 12333])
        "12 x 12,333.0"
        """
        result_str = ""
        for item in tokens:
            if isinstance(item, float):
                # number
                result_str += Human.number(item)#[:-2] # remove .0
            else:
                # operation
                result_str += f" {item.replace('*', 'x').replace('/', ':')} "
        return result_str
        

    def get_rnd_number(self) -> int:
        return random.randrange(self._min_number, self._max_number + 1)

    def get_rnd_symbol(self):
        return random.choice(self._allowed_symbols)

    def is_allowed(self, calc: str, end: bool = False) -> bool:
        try:    
            result = str(self.get_result(calc))
        except Exception:
            log.error(f"Can't calculate: {calc}")
            log.error(traceback.format_exc())
        if self._max_result_number:
            # check if number is too big
            too_big = float(result) >= self._max_result_number
            if not too_big:
                # check if number is too small 
                too_big = float(result) < self._max_result_number * -1
            if too_big:
                return False
        # check if number ends with allowed endings
        if end:
            # check only allowed endings
            return Multiple.endswith_(result, self._allowed_endings)
        else:
            # check allowed (partial) endings
            return Multiple.endswith_(result, [*self._allowed_partial_endings, *self._allowed_endings])

    def __str__(self) -> str:
        text = ""
        text += f"{Human.plural_('Operation', self._operations, with_number=True)} with \n{', '.join(f'`{s}`' for s in self._allowed_symbols)}\n"
        text += f"Numbers from `{self._min_number}` to `{self._max_number}`\n"
        text += f"and `{self._max_time}s/Task` time\n"
        if self._max_result_number:
            text += f"The will be smaller than `{self._max_result_number}`\n"
        text += f"Example: \n`{self.get_task()[1]}`"
        return text
    
    def __eq__(self, __o: Type[Self]) -> bool:
        return self.name == __o.name


plugin = lightbulb.Plugin("mind_training", "Contains calcualtion commands")

bot: Optional[Inu] = None

# all CalculationBlueprints for the game
# key is display name
stages = [
    CalculationBlueprint(
        max_number=9,
        operations=1,
        max_time=10,
        allowed_partial_endings=[],
        allowed_endings=[".0"],
        name="Stage 1",
        display_name="Stage 1️⃣",

    ),
    CalculationBlueprint(
        max_number=9,
        operations=2,
        max_time=20,
        allowed_partial_endings=[],
        allowed_endings=[".0"],
        name="Stage 2",
        display_name="Stage 2️⃣",
    ),
    CalculationBlueprint(
        max_number=15,
        operations=2,
        max_time=25,
        allowed_partial_endings=[".5"],
        allowed_endings=[".0"],
        name="Stage 3",
        max_result_number=500,
        display_name="Stage 3️⃣",
    ),
    CalculationBlueprint(
        max_number=10000,
        min_number=100,
        operations=1,
        max_time=60,
        allowed_partial_endings=[".5"],
        allowed_endings=[".0"],
        name="Stage 4",
        allowed_symbols=["+", "-"],
        display_name="Stage 4️⃣\n_--Big Numbers--_",
    ),
    CalculationBlueprint(
        max_number=40,
        min_number=5,
        operations=1,
        max_time=50,
        allowed_partial_endings=[".5"],
        allowed_endings=[".0"],
        name="Stage 5",
        allowed_symbols=["*"],
        display_name="Stage 5️⃣ \n_--Multiply Big--_",
    ),
    CalculationBlueprint(
        max_number=10,
        min_number=1,
        operations=3,
        max_time=70,
        allowed_partial_endings=[".5"],
        allowed_endings=[".0"],
        name="Stage 6",
        allowed_symbols=["*"],
        display_name="Stage 6️⃣\n_--Multiply Many--_",
    ),
    CalculationBlueprint(
        max_number=15,
        min_number=1,
        operations=6,
        max_time=60,
        max_result_number=2000,
        allowed_symbols=["+", "-", "*", "/"],
        allowed_partial_endings=[".0"],
        allowed_endings=[".0", "0.5"],
        name="Stage 7",
        display_name="Stage 7️⃣\n_--Many Operations--_",
    ),
    CalculationBlueprint(
        max_number=1,
        min_number=0,
        operations=1,
        max_time=99,
        allowed_symbols=["+"],
        allowed_partial_endings=[],
        allowed_endings=[".0"],
        name="Stage Artur",
        display_name="Stage Artur\n_--for intelligent individuals--_",
    ),


]

active_sessions: Set[hikari.Snowflakeish] = set()
@plugin.command
@lightbulb.command("math", "Menu with all calculation tasks I have")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def calculation_tasks(ctx: Context):
    embed = Embed(title="Calculation tasks")
    menu = MessageActionRowBuilder().add_text_menu("calculation_task_menu")
    for c in stages:
        embed.add_field(f"{c.display_name}", str(c), inline=True)
        menu.add_option(f"{c.display_name.replace('_', '')}", f"{c.name}")
    menu = menu.parent
    buttons = MessageActionRowBuilder().add_interactive_button(
        ButtonStyle.PRIMARY, 
        "math_highscore_btn",
        label="Highscores"
    )
    if bot is None:
        raise RuntimeError
    await ctx.respond(embed=embed, components=[menu, buttons])
    stage, _, cmp_interaction = await bot.wait_for_interaction(
        custom_ids=["calculation_task_menu", "math_highscore_btn"], 
        user_id=ctx.user.id, 
        channel_id=ctx.channel_id,
    )
    log.debug(stage)
    if not stage:
        return
    elif stage == "math_highscore_btn":
        await cmp_interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
        await show_highscores("guild" if ctx.guild_id else "user", ctx, cmp_interaction)
        return
    else:
        # prevent user from running multiple sessions
        if ctx.user.id in active_sessions:
            return await ctx.respond(f"You already play a game. End it with `stop! or wait`")
        else:
            active_sessions.add(ctx.user.id)

        await cmp_interaction.create_initial_response(
            ResponseType.MESSAGE_CREATE, 
            f"Well then, let's go!\nIt's not over when you calculate wrong\nYou can always stop with `stop!`"
        )
        c = get_calculation_blueprint(stage)
        highscore = await execute_task(ctx, c)
        # insert highscore
        await MathScoreManager.maybe_set_record(
            ctx.guild_id or 0,
            ctx.user.id,
            c.name,
            highscore,
        )
        # session is over - delete it
        try:
            active_sessions.remove(ctx.user.id)
        except ValueError:
            log.error(traceback.format_exc())
    

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
    resume_task_creation = True
    while resume_task_creation:
        # new task
        # this embed is not redundant, since it will be needed to get initial message
        # which will be edited later on
        current_task, current_task_beautiful = c.get_task()
        log.debug(f"{current_task=}; {current_task_beautiful=}")
        embed = Embed(title=f"What is {current_task_beautiful} ?")
        embed.color = Colors.from_name("green")
        msg = await ctx.respond(embed=embed)
        tasks: List[asyncio.Task] = []

        # add 3 embeds with different colors, which will be cycled according to rest time
        colors = ["yellow", "orange", "red"]
        for x in range(3):
            embed = Embed(title=f"What is {current_task_beautiful} ?")
            embed.color = Colors.from_name(colors[x])
            when = (x+1) * (c._max_time / 4)
            tasks.append(
                asyncio.create_task(
                    _change_embed_color(msg, embed, when)
                )
            )

        answer = ""
        expire_time = datetime.now() + timedelta(seconds=c._max_time)
        current_task_result = float(c.get_result(current_task))
        
        def time_is_up() -> bool:
            return datetime.now() > expire_time

        while answer != current_task_result and not time_is_up():
            answer, event = await bot.wait_for_message(
                timeout=expire_time.timestamp() - time(),
                channel_id=ctx.channel_id,
                user_id=ctx.user.id,
            )

            # stopped by timeout
            if not event:
                continue

            log.debug(f"{answer=}, {event.author.username=}, {current_task_result=}")
            # stopped by user
            answer = answer.replace(",", ".")
            if answer.strip().lower() == "stop!":
                resume_task_creation = False
                break

            # compare
            try:
                answer = float(answer.strip())
                if answer == current_task_result:
                    await event.message.add_reaction("✅")
                else:
                    await event.message.add_reaction("❌")
            except Exception:
                # answer is not a number -> ignore
                pass

        for task in tasks:
            task.cancel()
        if time_is_up() or not resume_task_creation:
            resume_task_creation = False
        else:
            tasks_done += 1
    if tasks_done == 0 and c.name in ["Stage 1", "Stage 2"]:
        await ctx.respond(
            f"You really solved nothing? Stupid piece of shit and waste of my precious time"
        )
    else:
        await ctx.respond(
            f"You solved {Human.plural_('task', tasks_done)}. The last answer was {Human.number(c.get_result(current_task))}"
        )
    return tasks_done

def get_calculation_blueprint(stage_name: str) -> CalculationBlueprint:
    for stage in stages:
        if stage.name == stage_name:
            return stage

async def show_highscores(from_: str, ctx: Context, i: ComponentInteraction):
    stages = await MathScoreManager.fetch_highscores(
        type_=from_,
        guild_id=ctx.guild_id or 0,
        user_id=ctx.user.id,
    )
    embeds: List[Embed] = []
    medals = {
        0: "🥇",
        1: "🥈",
        2: "🥉",
    }
    for i, d in enumerate(stages.items()):
        stage, highscore_dicts = d
        log.debug(d)
        if i % 24 == 0:
            embeds.append(
                Embed(title=f"🏆 Highscores", color=Colors.random_color())
            )
        if ctx.guild_id:
            value = (
                "\n".join(
                    [
                        f"{medals.get(i, '')}{(await bot.mrest.fetch_member(ctx.guild_id, u_id)).display_name:<25} {score:>}" 
                        for i,  d in enumerate(highscore_dicts) for u_id, score in d.items() if i < 5
                    ]
                )
            )
        else:
            value = (
                "\n".join(
                    [
                        f"{medals.get(i, '')}{(await bot.mrest.fetch_user(u_id)).display_name:<25} {score:>}" 
                        for i,  d in enumerate(highscore_dicts) for u_id, score in d.items() if i < 5
                    ]
                )
            )
        embeds[-1].add_field(get_calculation_blueprint(stage).display_name, f"```{value}```", inline=False)
    pag = Paginator(page_s=embeds)
    await pag.start(ctx)


def load(inu: Inu):
    inu.add_plugin(plugin)
    global bot
    bot = inu






