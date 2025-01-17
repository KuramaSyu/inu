
import asyncio
from datetime import datetime, timedelta
import random
from time import time
import traceback
from typing_extensions import Self
from typing import *

import hikari
from hikari import (
    Embed,
    ResponseType, 
    TextInputStyle,
    Permissions,
    ButtonStyle
)
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb import Context, Loader, Group, SubGroup, SlashCommand, invoke
from lightbulb.prefab import sliding_window

from core.bot import Inu, getLogger
from utils.language import Human
import tabulate

from utils import (
    NumericStringParser,
    Multiple, 
    Colors, 
    MathScoreManager, 
    Paginator
)

from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger,
    InuContext,
    get_context,
    ResponseProxy
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


loader = lightbulb.Loader()

bot: Optional[Inu] = None

# all CalculationBlueprints for the game
# key is display name
# name is inserted in the database -> must be unique
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
        max_number=25,
        min_number=10,
        operations=1,
        max_time=35,
        allowed_symbols=["*"],
        allowed_partial_endings=[".0"],
        allowed_endings=[".0"],
        name="Stage 8",
        display_name="Stage 8️⃣\n_--25 x 25--_",
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


@loader.listener(hikari.InteractionCreateEvent)
async def on_math_task_click(event: hikari.InteractionCreateEvent):
    """
    Listens to the /math menu and starts the math tasks
    """
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    ctx = get_context(event)
    custom_id = event.interaction.custom_id
    if custom_id == "math_highscore_btn":
        await ctx.defer()
        await show_highscores("guild" if ctx.guild_id else "user", ctx)
    elif custom_id == "calculation_task_menu":
        stage = event.interaction.values[0]
        await start_math_tasks(ctx, stage)
        


active_sessions: Set[hikari.Snowflakeish] = set()

@loader.command
class CommandName(
    SlashCommand,
    name="math",
    description="Menu with all calculation tasks I have",
    dm_enabled=False,
    default_member_permissions=None,
    hooks=[sliding_window(3, 1, "user")]
):

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        embed = Embed(title="Calculation tasks")
        embed.set_footer("Stop by writing 'stop!'")
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
        await ctx.respond(embed=embed, components=[menu, buttons])


async def start_math_tasks(ctx: InuContext, stage: str):
    # prevent user from running multiple sessions
    if ctx.user.id in active_sessions:
        return await ctx.respond(f"You already play a game. End it with `stop! or wait`")
    else:
        active_sessions.add(ctx.user.id)

    await ctx.respond(
        f"Well then, let's go!\nIt's not over when you calculate wrong\nYou can always stop with `stop!`",
        delete_after=60,
    )
    c = get_calculation_blueprint(stage)
    highscore, time_needed = await execute_task(ctx, c)
    # insert highscore
    if highscore > 0:
        await MathScoreManager.maybe_set_record(
            ctx.guild_id or 0,
            ctx.user.id,
            c.name,
            highscore,
            time_needed
        )
    # session is over - delete it
    try:
        active_sessions.remove(ctx.user.id)
    except ValueError:
        log.error(traceback.format_exc())
    

async def _change_embed_color(msg: ResponseProxy, embed: Embed, in_seconds: int | float):
    await asyncio.sleep(in_seconds)
    await msg.edit(embed=embed)


async def execute_task(ctx: InuContext, c: CalculationBlueprint) -> Tuple[int, timedelta]:
    """
    Executes a task and returns the number of tasks finished and the total time taken.

    Parameters:
    -----------
    - ctx (InuContext): The context object containing information about the command execution.
    - c (CalculationBlueprint): The calculation blueprint object.

    Returns:
    --------
    - tasks_done (int): The number of tasks finished.
    - total_time (timedelta): The total time taken to finish the tasks.
    """
    bot = ctx.bot
    if bot is None:
        raise RuntimeError(f"Inu is None") # should never happen
    tasks_done = 0
    resume_task_creation = True
    message_ids: List[hikari.Snowflake] = []
    total_time = timedelta(seconds=0)
    current_task_beautiful = ""
    current_task = ""

    while resume_task_creation:
        # new task
        # this embed is not redundant, since it will be needed to get initial message
        # which will be edited later on
        start_time = datetime.now()
        current_task, current_task_beautiful = c.get_task()
        embed = Embed(title=f"What is {current_task_beautiful} ?")
        embed.color = Colors.from_name("green")
        msg = await ctx.respond(embed=embed)
        message_ids.append((await msg.message()).id)
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
                timeout=expire_time.timestamp() - time(),  # type:ignore
                channel_id=ctx.channel_id,
                user_id=ctx.user.id,
            )
            
            # stopped by timeout
            if not event:
                continue
            
            message_ids.append(event.message_id)
            log.debug(f"{answer=}, {event.author.username=}, {current_task_result=}")
            # stopped by user
            assert answer is not None
            answer = answer.replace(",", ".")
            if answer.strip().lower() == "stop!":
                resume_task_creation = False
                break

            # compare
            try:
                answer = float(answer.strip())
                if answer == current_task_result:
                    await event.message.add_reaction("✅")
                    total_time += datetime.now() - start_time
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

    purge_delete_button = purge_components(delete=True, repeat=True, message_ids=message_ids)
    final_response = None
    if tasks_done == 0 and c.name in ["Stage 1", "Stage 2"]:
        final_response = await ctx.respond(
            f"You really solved nothing? Stupid piece of shit and waste of my precious time",
            components=purge_delete_button
        )
    else:
        embed = hikari.Embed(title=f"{ctx.member.display_name}'s results for {c.display_name}")  # type: ignore
        embed.add_field("Tasks solved:", f"```\n{Human.plural_('task', tasks_done)}```")
        time_per_task = 0
        try:
            time_per_task = float(total_time.total_seconds() / tasks_done)
        except ZeroDivisionError:
            pass
        embed.add_field("Time per Task:", f"```\n{time_per_task:.2f} seconds / Task```")
        embed.add_field("Last Task:", f"Task: {current_task_beautiful}\nResult: {Human.number(c.get_result(current_task))}")
        embed.set_thumbnail(ctx.author.avatar_url)
        final_response = await ctx.respond(embed=embed, components=purge_delete_button)

    async def maybe_clean_up(messages: List[hikari.Snowflake], message_id: int, channel_id: int):
        delete = True
        repeat = True
        bot = Inu.instance
        while True:
            try:
                custom_id, event, _ = await bot.wait_for_interaction(
                    custom_ids=["math_bulk_delete", "calculation_task_repeat"],
                    message_id=message_id,
                    timeout=60*10
                )
            except asyncio.TimeoutError:
                break
            assert event is not None
            ctx = get_context(event)
            if custom_id == "math_bulk_delete":
                delete = False
                # split messages in 100 message chunks and delete those
                sub_lists = []
                for i, m in enumerate(messages):
                    if i % 100 == 0:
                        sub_lists.append([])
                    sub_lists[-1].append(m)
                for sub_list in sub_lists:
                    await bot.rest.delete_messages(channel_id, sub_list)
                await ctx.respond(components=purge_components(delete=delete, repeat=repeat, message_ids=message_ids), update=True)
            elif custom_id == "calculation_task_repeat":
                repeat = False
                await ctx.respond(components=purge_components(delete=delete, repeat=repeat, message_ids=message_ids), update=True)
                await start_math_tasks(ctx, c.name)


    asyncio.create_task(maybe_clean_up(
            message_ids, (await final_response.message()).id, ctx.channel_id
    ))

    return tasks_done, timedelta(seconds=total_time.total_seconds())

def purge_components(delete: bool, repeat: bool, message_ids: List[hikari.Snowflake]):
    return [
        MessageActionRowBuilder()
        .add_interactive_button(ButtonStyle.PRIMARY, "math_bulk_delete", label=f"Clean up messages ({len(message_ids)})", emoji="🗑️", is_disabled=not delete)
        .add_interactive_button(ButtonStyle.PRIMARY, "calculation_task_repeat", label="Repeat this stage", emoji="🔁", is_disabled=not repeat)
    ]


def get_calculation_blueprint(stage_name: str) -> CalculationBlueprint:
    for stage in stages:
        if stage.name == stage_name:
            return stage
    raise ValueError(f"Stage {stage_name} not found")



async def show_highscores(from_: str, ctx: InuContext):
    bot = Inu.instance
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
        stage, records = d
        log.debug(f"{d}")
        if i % 24 == 0:
            embeds.append(
                Embed(title=f"🏆 Highscores", color=Colors.random_color())
            )
        results = []
        for i, content in enumerate(records):
            if i > 8:
                break
            user_id, score, time_per_task = content
            name_short = ""
            if ctx.guild_id:
                name_short = Human.short_text(
                    (await bot.mrest.fetch_member(ctx.guild_id, user_id)).display_name, 25, ".."  # type: ignore
                )
            else:
                name_short = Human.short_text(
                    (await bot.mrest.fetch_user(user_id)).display_name, 25, ".." # type: ignore
                )
            results.append((i+1, name_short, score, f"{time_per_task.total_seconds():.2f}s"))

        value = tabulate.tabulate(
            results, 
            [" ", "Name", "Score", "Time/Task"],
            tablefmt="rounded_grid",
            colalign=("left", "left", "center", "center")


        )
        if embeds[-1].total_length() + len(value) > 6000:
            embeds.append(
                Embed(title=f"🏆 Highscores", color=Colors.random_color())
            )
        embeds[-1].add_field(get_calculation_blueprint(stage).display_name, f"```{value}```", inline=False)
    pag = Paginator(page_s=embeds)
    await pag.start(ctx)






