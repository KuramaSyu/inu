from argparse import ArgumentError
import contextlib
from datetime import datetime
from inspect import getmembers, getsource
import io
import os
import traceback
import typing
import asyncio

import hikari
import lightbulb

import logging

from utils import crumble
from utils import Paginator
from utils.tree import tree as tree_
from core import Inu
log = logging.getLogger(__name__)


class Owner(lightbulb.Plugin):
    """
    A class wich is only accessable to the Owner
    """
    def __init__(self, bot: Inu):
        self.bot = bot
        super().__init__(name="Owner Commands")

    @lightbulb.listener(hikari.StartedEvent)
    async def start(self, event):
        await asyncio.sleep(5)


    @lightbulb.check(lightbulb.owner_only) #type: ignore
    @lightbulb.group()
    async def sql(self, ctx: lightbulb.Context, *, sql: str):
        """
        executes sql
        Parameters:
        code: your code to execute
        args: your arguments if needed

        NOTE:
        -----
            - seperate sql from args with ";;", seperate every arg with ","
        """

        code = self.build_sql(sql, "execute")
        await self._execute(ctx, code)

    @lightbulb.check(lightbulb.owner_only) #type: ignore
    @sql.command(aliases=["-r"])
    async def fetch(self, ctx: lightbulb.Context, *, sql: str):
        """
        fetches sql (returns something)
        Parameters:
        code: your code to execute
        args: your arguments if needed

        NOTE:
        -----
            - seperate sql from args with ";;", seperate every arg with ","
        """
        code = self.build_sql(sql, "fetch")
        await self._execute(ctx, code)


    def build_sql(self, sql: str, method: str) -> str:
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


    @lightbulb.command(name = "log")
    async def log(self, ctx):
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
        for page in shorted:
            embed = hikari.Embed()
            embed.description = f"```py\n{page}\n```"
            embeds.append(f"```py\n{page}\n```")
        paginator = Paginator(page_s=embeds, timeout=10*60)
        await paginator.start(ctx)

    @lightbulb.check(lightbulb.owner_only) #type: ignore
    @lightbulb.command(aliases=['py', 'exec', 'run'])
    async def execute(self, ctx: lightbulb.Context, *, code: str):
        '''
        executes code
        Parameters:
        code: your code to execute
        '''
        await self._execute(ctx, code)

    async def _execute(self, ctx: lightbulb.Context, code: str):
        env = {
            'client': self.bot,
            'bot': self.bot,
            'db': self.bot.db,
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
        raw_code = await self.clean_code(code)
        code, fn_name = await self.wrap_into_async(await self.clean_code(code))
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

    @staticmethod
    async def clean_code(code):
        while code.startswith("`"):
            code = code[1:]
        while code.endswith("`"):
            code = code[:-1]
        while code.startswith("py\n"):
            code = code[3:]
        return code

    async def wrap_into_async(self, code):
        func_name = '_to_execute'
        code = "\n".join(f"    {line}" for line in code.splitlines())
        return f"async def {func_name}():\n{code}", func_name




def load(bot: Inu):
    bot.add_plugin(Owner(bot))
