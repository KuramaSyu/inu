import contextlib
from datetime import datetime
from inspect import getmembers, getsource
import io
import os
import traceback
import typing
import asyncio
import logging


import hikari
import lightbulb
from lightbulb.context import Context
from lightbulb import commands
from lightbulb.commands import OptionModifier as OM

from utils import crumble
from utils import Paginator
from utils.tree import tree as tree_
from core import Inu

log = logging.getLogger(__name__)

plugin = lightbulb.Plugin("Owner Only", "Commands, which are only accessable to the owner of the bot")


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
    code = build_sql(ctx.options.sql, "execute")
    await _execute(ctx, code)

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
    sql = ctx.options.sql
    code = build_sql(sql, "fetch")
    await _execute(ctx, code)


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
@lightbulb.command("log", "Shows the log of the entire me")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def log_(ctx: Context):
    """
    Shows my LOG file
    """
    inu_log_file = open(f"{os.getcwd()}/inu/inu.log", mode="r", encoding="utf-8")
    try:
        inu_log = inu_log_file.read()
        inu_log.encode("utf-8")
    except Exception:
        log.error(traceback.format_exc())
        return
    inu_log_file.close()
    shorted = crumble(inu_log, max_length_per_string=1980)

    embeds = []
    for i, page in enumerate(shorted):
        description = f"```py\n{page}\n```page {i+1}/{len(shorted)}"
        embeds.append(description)
    paginator = Paginator(page_s=embeds, timeout=10*60)
    await paginator.start(ctx)

@plugin.command
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.option("code", "The code I should execute", modifier=OM.CONSUME_REST)
@lightbulb.command("run", "Executes given Python code", aliases=['py', 'exec'])
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def execute(ctx: Context):
    '''
    executes code
    Parameters:
    code: your code to execute
    '''
    code = ctx.options.code
    await _execute(ctx, code)

async def _execute(ctx: Context, code: str):
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

    # cleans code and wraps into async
    raw_code = await clean_code(code)
    code, fn_name = await wrap_into_async(await clean_code(code))
    log.warning(f"code gets executed:\n<<<\n{code}\n>>>")
    exec(compile(code, "<string>", mode='exec'), env)
    func = env[fn_name]

    error = None
    str_obj = io.StringIO()
    start = datetime.now()
    output = None

    try:
        with contextlib.redirect_stdout(str_obj):
            start = datetime.now()
            await func()
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

        basic_message = f'**CODE**\n```py\n{raw_code}```\n'
        if error:
            basic_message += f'\n{error}\n'
        if not output or len(output) < 1800:
            basic_message += f'**OUTPUT**\n```py\n{output if output else None}```\n'
            basic_message += f'{round(ms, 4)} ms'
            embeds = []
            for page in crumble(basic_message, 1950):
                em = hikari.Embed(description=page)
                embeds.append(em)
            pag = Paginator(embeds)
            await pag.start(ctx)
            return

        pages = []
        cutted = crumble(output, max_length_per_string=1800)
        for index, part_message in enumerate(cutted):
            embed = hikari.Embed()
            embed.title = f'Execution {index + 1}/{len(cutted)}'
            embed.description = f'**OUTPUT**\n```py\n{part_message}```\n'

            if index == 0:
                embed.add_field(
                    name='CODE',
                    value=f'```py\n{raw_code}```\n',
                    inline=False
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

        paginator = Paginator(page_s=pages, timeout=600)
        await paginator.start(ctx)


async def clean_code(code):
    while code.startswith("`"):
        code = code[1:]
    while code.endswith("`"):
        code = code[:-1]
    while code.startswith("py\n"):
        code = code[3:]
    return code

async def wrap_into_async(code):
    func_name = '_to_execute'
    code = "\n".join(f"    {line}" for line in code.splitlines())
    return f"async def {func_name}():\n{code}", func_name




def load(bot: Inu):
    bot.add_plugin(plugin)
