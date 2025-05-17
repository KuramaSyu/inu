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
from hikari import ApplicationContextType
import lightbulb
from lightbulb.context import Context
from lightbulb import AutocompleteContext, SlashCommand, invoke
from expiring_dict import ExpiringDict
import lightbulb.prefab.checks

from utils import crumble
from utils import Paginator
from utils.tree import tree as tree_
from core import Inu, InuContext
from utils import BaseReminder, HikariReminder, Reminders, Human, Multiple
from utils.string_crumbler import NumberWordIterator as NWI
from core import getLogger, get_context


log = getLogger(__name__)

bot = Inu.instance
plugin = lightbulb.Loader()
LOG_LEVELS = {"DEBUG":1, "INFO":2, "WARNING":3, "ERROR":4, "CRITICAL":5}
all_levels = list(LOG_LEVELS.keys())

# specific for run command - only for response update on message edit
message_id_cache: ExpiringDict[int, Tuple[Callable, InuContext, Paginator]] = ExpiringDict(ttl=60*120)  # type: ignore


def strip_code(code: str) -> str | None:
    if "run " in code:
        code = code.split(" ", 1)[-1]
    elif "run\n" in code:
        code = code.split("\n", 1)[-1]
    else:
        return None
    return code

@plugin.listener(hikari.events.MessageUpdateEvent)
async def on_message_update(event: hikari.events.MessageUpdateEvent):
    if not event.message_id in message_id_cache:
        return
        
    # I know, that this is a nasty way
    ctx: InuContext
    _, ctx, _ = message_id_cache[event.message_id]
    content = event.message.content
    if not content:
        return
    code = None
    if "run " in content:
        code = content.split(" ", 1)[-1]
    elif "run\n" in content:
        code = content.split("\n", 1)[-1]
    else:
        return
    await ExecuteCommand.execute_callback(ctx, code)
    
@plugin.listener(hikari.events.MessageCreateEvent)
async def on_message_create(event: hikari.events.MessageCreateEvent):
    if event.author_id not in [362262726191349761]:
        return
    ctx = get_context(event)
    content = (await ctx.message()).content
    if not content:
        return
    
    code = None
    code = strip_code(content)
    if not code:
        return
    await ExecuteCommand.execute_callback(ctx, code)
    
    

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



loader = lightbulb.Loader()
bot: Inu

async def log_level_autocomplete(ctx: AutocompleteContext) -> None:
    await ctx.respond(all_levels) 

sql_group = lightbulb.Group("sql", description="Commands for SQL queries")

@sql_group.register
class SqlFetchCommand(
    lightbulb.SlashCommand,
    name="return",
    description="executes SQL with return",
    hooks=[lightbulb.prefab.checks.owner_only],
    contexts=[ApplicationContextType.GUILD]
):
    sql = lightbulb.string("sql", "The SQL query you want to execute. Good for selection querys")
    
    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        sql_and_values = self.sql.split(";;")
        sql = sql_and_values[0]
        values = ""
        if len(sql_and_values) > 1:
            values += f"```\n{sql_and_values[1]}\n```"
        code = build_sql(self.sql, "fetch")
        await ctx.defer()
        page_s, ms = await _execute(ctx, code, add_code_to_embed=False)
        if not page_s[0]._fields:
            page_s[0]._fields = []
        page_s[0]._fields.insert(0, hikari.EmbedField(name="SQL", value=f"```sql\n{sql}```"))
        if values:
            page_s[0]._fields.insert(1, hikari.EmbedField(name="Values", value=values))
        pag = Paginator(page_s=page_s)
        await pag.start(ctx)

@loader.command
class LogCommand(
    lightbulb.SlashCommand,
    name="log",
    description="Shows the log of the entire me",
    contexts=[ApplicationContextType.GUILD, ApplicationContextType.PRIVATE_CHANNEL],
    hooks=[lightbulb.prefab.checks.owner_only]
):
    level_stop = lightbulb.string("level-stop", "the last level to show", default="CRITICAL", autocomplete=log_level_autocomplete)
    level_start = lightbulb.string("level-start", "the lowest level to show", default="INFO", autocomplete=log_level_autocomplete)

    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await ctx.defer()
        levels_to_use = [
            k for k, v in LOG_LEVELS.items() 
            if v >= LOG_LEVELS[self.level_start] 
            and v <= LOG_LEVELS[self.level_stop]
        ]

        # ...rest of log command implementation...
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
        embeds = []
        for i, page in enumerate(shorted):
            description = f"```py\n{page}\n```page {i+1}/{len(shorted)}"
            embeds.append(description)
        paginator = Paginator(page_s=embeds, timeout=10*60, download=inu_log, default_page_index=-1)
        await paginator.start(ctx)



@loader.command
class ExecuteCommand(
    lightbulb.SlashCommand,
    name="run",
    description="Executes given Python code",
    contexts=[ApplicationContextType.GUILD],
    hooks=[lightbulb.prefab.checks.owner_only]
):
    code = lightbulb.string("code", "The code I should execute")

    @lightbulb.invoke 
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await ExecuteCommand.execute_callback(ctx, self.code)

    @staticmethod
    async def execute_callback(ctx: InuContext, code: str):
        ctx.enforce_update(True)
        await ctx.defer(background=False)
        page_s, ms = await _execute(ctx, code)
        
        if len(page_s) > 5:
            kwargs = {"disable_search_btn": True, "compact": False}
        else:
            kwargs = {"compact": True}
        _, _, pag = message_id_cache.get(ctx.id, (None, None, None))
        try:
            await pag.delete_presence()
        except Exception:
            pass
        pag = Paginator(
            page_s=page_s, 
            disable_paginator_when_one_site=False, 
            timeout=10*60,
            **kwargs,  # type: ignore
        )
        message_id_cache[ctx.id] = (ExecuteCommand.execute_callback, ctx, pag)
        await pag.start(ctx)




async def _execute(ctx: InuContext, code: str, add_code_to_embed: bool = True) -> Tuple[List[hikari.Embed], float]:
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
        'client': bot,
        'bot': bot,
        'db': bot.db,
        'ctx': ctx,
        'p': print,
        'getmembers': getmembers,
        'getsource': getsource,
        's_dir':
        lambda obj, search: [attr for attr in dir(obj) if search in attr],
        'tree':
        lambda obj=None, depth=0, search='', docs=False, private=False: 
            tree_(
                obj=obj,
                search_for=search, 
                with_docs=docs, 
                with_private=private, 
                depth=depth
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
    cleaned_code = ""

    error = None
    str_obj = io.StringIO()
    start = datetime.now()
    output = None
    traceback_list = []

    try:
        wraped_code, cleaned_code, parsed, fn_name = clean_code(code)
        log.warning(f"/run used by {ctx.author.username} [{ctx.author.id}]", prefix="owner")
        exec(compile(parsed, filename="<eval>", mode='exec'), env)
        func = env[fn_name]
        start = datetime.now()
        with contextlib.redirect_stdout(str_obj):
            result = str(await func())

        if result == "None":
            result = None
        output = str_obj.getvalue()

    except Exception as e:
        traceback_list = traceback.format_tb(e.__traceback__)
        traceback_list.insert(0, f"{e.__class__.__name__}: {e}")


    finally:
        embeds: List[hikari.Embed] = []
        timedelta = datetime.now() - start
        ms = int(round(timedelta.total_seconds() * 1000, 2))

        # create duration time str
        if timedelta.total_seconds() * 1000 < 2:
            time_str = f"{round(timedelta.total_seconds() * 1000 * 1000)} ns"
        elif timedelta.total_seconds() < 10:
            # below 10s
            time_str = f"{round(timedelta.total_seconds() * 1000, 2)} ms"
        else:
            time_str = f"{round(timedelta.total_seconds(), 2)} s"

        # fix output
        if output is None:
            output = str_obj.getvalue()

        # add return value
        if result:
            for partial_result in crumble(result, 1950):
                em = hikari.Embed(description=f"**RETURNED**\n```py\n{partial_result}```\n")
                embeds.append(em)

        # add code
        if add_code_to_embed:
            if (
                len(cleaned_code) < 1000 and len(embeds) > 0 
                and len(str(embeds[0].description)) + len(cleaned_code) < 2000 
                and str(output) in ["", "None"]
            ):
                em = embeds[0]
                em.description = f'{em.description or ""}**CODE**\n'
            else:
                em = hikari.Embed(description="**CODE**\n")
                embeds.append(em)
            em.description = f'{em.description or ""}```py\n{cleaned_code}```\n'

        # add stdout
        if output and str(output) != "None":
            for partial_output in crumble(output, 1950):
                em = hikari.Embed(description=f"**OUTPUT**\n```py\n{partial_output}```\n")
                embeds.insert(-1, em)

        # add errors
        if traceback_list:
            error_ems = []
            for index, tb in enumerate(traceback_list):
                if index % 20 == 0:
                    error_ems.append(hikari.Embed(title="ERROR"))
                error_ems[-1].add_field(f"_Traceback - layer {index + 1}_", f'```py\n{tb}```')
            if len(embeds) >= 1:
                embeds = [*embeds[:-1], *error_ems, embeds[-1]]
            else:
                embeds = error_ems
        
        # add duration
        if len(embeds) == 0:
            embeds.append(hikari.Embed())
        embeds[0].set_footer(time_str)
        return embeds, round(ms, 4)


def clean_code(code) -> Tuple[str, str, ast.Module, str]:
    """
    Cleans the given code by removing leading and trailing backticks, as well as the 'py' prefix if present.
    Wraps the cleaned code into an async function and returns the cleaned code, the original code without async,
    the parsed AST, and the name of the function.

    Args:
        code (str): The code to be cleaned.

    Returns:
        Tuple[str, str, ast.AST, str]: A tuple containing the cleaned code, the original code without async,
        the parsed AST, and the name of the function.
    """
    while code.startswith("`"):
        code = code[1:]
    while code.endswith("`"):
        code = code[:-1]
    while code.startswith("py\n"):
        code = code[3:]
    un_asynced_code = code
    code, fn_name = wrap_into_async(code)
    # cleans code and wraps into async
    parsed = ast.parse(code)
    body = parsed.body[0].body  # type: ignore
    insert_returns(body)

    return code, un_asynced_code, parsed, fn_name

def wrap_into_async(code):
    func_name = '_to_execute'
    code = "\n".join(f"    {line}" for line in code.splitlines())
    return f"async def {func_name}():\n{code}", func_name
