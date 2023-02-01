from typing import *
import contextlib
from datetime import datetime
from inspect import getmembers, getsource
import io
import os
import traceback
import typing
import asyncio
import logging
import ast


import hikari
import lightbulb
from lightbulb.context import Context
from lightbulb import commands
from lightbulb.commands import OptionModifier as OM

from utils import crumble
from utils import Paginator
from utils.tree import tree as tree_
from core import Inu
from utils import BaseReminder, HikariReminder, Reminders, Human, Multiple
from utils.string_crumbler import NumberWordIterator as NWI
from core import getLogger, get_context


log = getLogger(__name__)

plugin = lightbulb.Plugin("Owner", "Commands, which are only accessable to the owner of the bot")
LOG_LEVELS = {"DEBUG":1, "INFO":2, "WARNING":3, "ERROR":4, "CRITICAL":5}
all_levels = list(LOG_LEVELS.keys())

# from norinorin: https://github.com/norinorin/nokari/blob/kita/nokari/extensions/extras/admin.py#L32-L50
def insert_returns(body: Union[List[ast.AST], List[ast.stmt]]) -> None:
    """A static method that prepends a return statement at the last expression."""

    if not body:
        return

    if isinstance(body[-1], ast.Expr):
        body[-1] = ast.Return(body[-1].value)
        ast.fix_missing_locations(body[-1])

    if isinstance(body[-1], ast.If):
        insert_returns(body[-1].body)
        insert_returns(body[-1].orelse)

    if isinstance(body[-1], ast.With):
        insert_returns(body[-1].body)

    if isinstance(body[-1], ast.AsyncWith):
        insert_returns(body[-1].body)



@plugin.command
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.option("sql", "The sql query you want to execute", modifier=OM.CONSUME_REST)
@lightbulb.command("sql", "executes SQL. NOTE: seperate sql from args with ';;' and sep. args with ','")
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def sql(ctx: Context):
    """
    executes sql
    Parameters:
    code: your code to execute
    args: your arguments if needed

    NOTE:
    -----
        - seperate sql from args with ";;", seperate every arg with ","
    """
    pass


@sql.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.option("sql", "The SQL query you want to execute. Good for selection querys", modifier=OM.CONSUME_REST)
@lightbulb.command("return", "executes SQL with return", aliases=["-r", "r", "fetch"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def fetch(ctx: Context):
    """
    fetches sql (returns something)
    Parameters:
    code: your code to execute
    args: your arguments if needed

    NOTE:
    -----
        - seperate sql from args with ";;", seperate every arg with ","
    """
    sql_and_values = ctx.options.sql.split(";;")
    sql = sql_and_values[0]
    values = ""
    if len(sql_and_values) > 1:
        values += f"```\n{sql_and_values[1]}\n```"
    code = build_sql(ctx.options.sql, "fetch")
    ctx = get_context(ctx.event)
    await ctx.defer()
    page_s, ms = await _execute(ctx, code, add_code_to_embed=False)
    if not page_s[0]._fields:
        page_s[0]._fields = []
    page_s[0]._fields.insert(0, hikari.EmbedField(name="SQL", value=f"```sql\n{sql}```"))
    if values:
        page_s[0]._fields.insert(1, hikari.EmbedField(name="Values", value=values))
    pag = Paginator(page_s=page_s)
    await pag.start(ctx)


def build_sql(sql: str, method: str) -> str:
    parts = sql.split(";;")
    if len(parts) == 1:
        line = f"'''{parts[0]}'''"
    elif len(parts) == 2:
        line = f"'''{parts[0]}''', {parts[1]}"
    else:
        raise TypeError("SQL string has more than 1x ';;' to devide sql from args")
    code = (
        f"from pprint import pprint\n"
        f"resp = await db.{method}(\n"
        f"{line}\n"
        f")\n"
        f"if resp is None: print('None')\n"
        f"else: pprint(resp)"
    )
    return code


@plugin.command
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.option("level-stop", "the last level to show", default="CRITICAL", autocomplete=True)
@lightbulb.option("level-start", "the lowest level to show", default="INFO", autocomplete=True)
@lightbulb.command("log", "Shows the log of the entire me")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def log_(ctx: Context):
    """
    Shows my LOG file
    """
    
    options = ctx.options
    ctx = get_context(ctx.event)
    await ctx.defer()
    levels_to_use = [
        k for k, v in LOG_LEVELS.items() 
        if v >= LOG_LEVELS[options["level-start"]] 
        and v <= LOG_LEVELS[options["level-stop"]]
    ]


    inu_log_file = open(f"{os.getcwd()}/inu/inu.log", mode="r", encoding="utf-8")
    try:
        inu_log = inu_log_file.read()
        inu_log.encode("utf-8")
    except Exception:
        log.error(traceback.format_exc())
        return
    inu_log_file.close()
    inu_log_filtered = ""
    append = False
    for line in inu_log.split("\n"):
        if Multiple.startswith_(line, levels_to_use):  # one of the wanted log levels
            append = True
        elif Multiple.startswith_(line, all_levels):  # one of the unwanted log levels
            append = False
        if append:
            inu_log_filtered += f"{line}\n"
    shorted = crumble(inu_log_filtered, max_length_per_string=1980, clean_code=True)
    shorted.reverse()
    embeds = []
    for i, page in enumerate(shorted):
        description = f"```py\n{page}\n```page {i+1}/{len(shorted)}"
        embeds.append(description)
    paginator = Paginator(page_s=embeds, timeout=10*60, download=inu_log)
    await paginator.start(ctx)

@plugin.command
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.option("code", "The code I should execute", modifier=OM.CONSUME_REST)
@lightbulb.command("run", "Executes given Python code", aliases=['py', 'exec', 'execute'])
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def execute(_ctx: Context):
    '''
    executes code
    Parameters:
    code: your code to execute
    '''
    code = _ctx.options.code
    ctx = get_context(_ctx.event)
    await ctx.defer(background=False)
    page_s, ms = await _execute(ctx, code)
    pag = Paginator(page_s=page_s)
    await pag.start(ctx)

async def _execute(ctx: Context, code: str, add_code_to_embed: bool = True) -> Tuple[List[hikari.Embed], float]:
    """
    executes the code.

    Returns:
    -------
    List[hikari.Embed] :
        the result of the execution wrapped into hikari.Embeds
    float :
        the time it took to execute
    """
    env = {
        'client': plugin.bot,
        'bot': plugin.bot,
        'db': plugin.bot.db,
        'ctx': ctx,
        'p': print,
        'getmembers': getmembers,
        'getsource': getsource,
        's_dir':
        lambda obj, search: [attr for attr in dir(obj) if search in attr],
        'tree':
        lambda obj=None, depth=0, search='', docs=False, private=False: print(
            tree_(
                obj=obj,
                search_for=search, 
                with_docs=docs, 
                with_private=private, 
                depth=depth
            )
        ),
        's_tree':
        lambda obj=None, search='', depth=0, docs=False, private=False: print(
            tree_(
                obj,
                search_for=search, 
                with_docs=docs, 
                with_private=private, 
                depth=depth
            )
        )
    }
    env.update(globals())
    result = None
    raw_code = code
    code, parsed, fn_name = clean_code(code)
    log.warning(f"code gets executed:\n<<<\n{code}\n>>>")
    exec(compile(parsed, filename="<eval>", mode='exec'), env)
    func = env[fn_name]

    error = None
    str_obj = io.StringIO()
    start = datetime.now()
    output = None

    try:
        with contextlib.redirect_stdout(str_obj):
            start = datetime.now()
            result = str(await func())
            if result == "None":
                result = None
            output = str_obj.getvalue()

    except Exception as e:
        error = f"**ERROR**\n```py\n{e.__class__.__name__}: {e}\n```"
        traceback_list = traceback.format_tb(e.__traceback__)
        for index, tb in enumerate(traceback_list):
            error += f'\n_Traceback - layer {index + 1}_\n```python\n{tb}```'
        output = str_obj.getvalue()

    finally:
        timedelta = datetime.now() - start
        ms = int(round(timedelta.total_seconds() * 1000))
        basic_message = ""
        if add_code_to_embed:
            basic_message = f'**CODE**\n```py\n{raw_code}```\n'
        if result:
            basic_message += f"**RETURN VALUE**\n```py\n{result}```\n"
        if error:
            basic_message += f'\n{error}\n'

        if not output or len(output) < 1800:
            basic_message += f'**OUTPUT**\n```py\n{output if output else None}```\n'
            basic_message += f'{round(ms, 4)} ms'
            embeds = []
            for page in crumble(basic_message, 1950):
                em = hikari.Embed(description=page)
                embeds.append(em)
            return embeds, round(ms, 4)

        pages = []
        if len(str(result)) > 1000:
            output = f"**RETURN VALUE**\n\n{result}\n\n"
            result = None

        cutted = crumble(output, max_length_per_string=1800)
        for index, part_message in enumerate(cutted):
            embed = hikari.Embed()
            embed.title = f'Execution {index + 1}/{len(cutted)}'
            embed.description = f'**OUTPUT**\n```py\n{part_message}```\n'

            if index == 0:
                if add_code_to_embed:
                    embed.add_field(
                        name='CODE',
                        value=f'```py\n{raw_code}```\n',
                        inline=False
                    )
                if result:
                    embed.add_field(
                        name="RETURN VALUE",
                        value=result,
                        inline=False,
                    )
                if error:
                    embed.add_field(
                        name='ERROR',
                        value=f'```py\n{error}```\n',
                        inline=False
                    )
                embed.add_field(
                    name='DURATION',
                    value=f'{ms} ms',
                    inline=False
                )

            pages.append(embed)

        return pages, round(ms, 4)


def clean_code(code) -> Tuple[str, ast.AST, str]:
    while code.startswith("`"):
        code = code[1:]
    while code.endswith("`"):
        code = code[:-1]
    while code.startswith("py\n"):
        code = code[3:]
    code, fn_name = wrap_into_async(code)
    # cleans code and wraps into async
    parsed = ast.parse(code)
    body = parsed.body[0].body  # type: ignore
    insert_returns(body)

    return code, parsed, fn_name

def wrap_into_async(code):
    func_name = '_to_execute'
    code = "\n".join(f"    {line}" for line in code.splitlines())
    return f"async def {func_name}():\n{code}", func_name

@log_.autocomplete("level-stop")
@log_.autocomplete("level-start")
async def tag_name_auto_complete(
    option: hikari.AutocompleteInteractionOption, 
    interaction: hikari.AutocompleteInteraction
) -> List[str]:
    return all_levels




def load(bot: Inu):
    bot.add_plugin(plugin)
