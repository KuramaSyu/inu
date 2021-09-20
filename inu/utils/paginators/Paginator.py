"""
MIT License

Copyright (c) 2021 Kur4m4
Copyright (c) 2020 Smyile

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import asyncio
from inspect import trace
from typing import List, Union, Optional
from contextlib import suppress
import re
import traceback
from functools import wraps

import discord
from discord import embeds
from discord.ext.commands.errors import BadArgument
from discord.ext.commands import Context


class Paginator:
    """A pagination wrapper that allows to move between multiple pages by using reactions.

    Attributes
    ------------
    pages: Optional[Union[:class:`List[discord.Embed]`, :class:`discord.Embed`]]
        A list of pages you want the paginator to paginate.
        Passing a discord.Embed instance will still work as if you were
        using: await ctx.send(embed=embed).
    timeout: :class:`float`.
        The timeout to wait before stopping the paginator session.
        Defaults to ``90.0``.
    compact: :class:`bool`.
        Whether the paginator should only use three reactions:
        previous, stop and next. Defaults to ``False``.
    has_input: :class:`bool`.
        Whether the paginator should add a reaction for taking input
        numbers. Defaults to ``True``.
    """

    __slots__ = (
        "pages",
        "timeout",
        "compact",
        "has_input",
        "message",
        "ctx",
        "bot",
        "loop",
        "current",
        "previous",
        "end",
        "reactions",
        "__tasks",
        "__is_running",
    )

    def __init__(
        self,
        *,
        pages: Optional[Union[List[discord.Embed], discord.Embed]] = None,
        compact: bool = False,
        timeout: float = 90.0,
        has_input: bool = True,
    ):
        self.pages = pages
        self.compact = compact
        self.timeout = timeout
        self.has_input = has_input

        self.ctx = None
        self.bot = None
        self.loop = None
        self.message = None

        self.current = 0
        self.previous = 0
        self.end = 0
        self.reactions = {
            "⏮": 0.0,
            "◀": -1,
            "⏹️": "stop",
            "▶": +1,
            "⏭": None,
        }

        self.__tasks = []
        self.__is_running = True

        if self.has_input is True:
            self.reactions["🔢"] = "input"

        if self.pages is not None:
            if len(self.pages) == 2:
                self.compact = True

        if self.compact is True:
            keys = ("⏮", "⏭", "🔢")
            for key in keys:
                try:
                    del self.reactions[key]
                except KeyError:
                    pass

    def go_to_page(self, number):
        if number > int(self.end):
            page = int(self.end)
        else:
            page = number - 1
        self.current = page

    async def controller(self, react):
        if react == "stop":
            await self.stop()

        elif react == "input":
            to_delete = []
            message = await self.ctx.send("What page do you want to go to?")
            to_delete.append(message)

            def check(m):
                if m.author.id != self.ctx.author.id:
                    return False
                if self.ctx.channel.id != m.channel.id:
                    return False
                if not m.content.isdigit():
                    return False
                return True

            try:
                message = await self.bot.wait_for("message", check=check, timeout=30.0)
            except asyncio.TimeoutError:
                to_delete.append(
                    await self.ctx.send("You took too long to enter a number.")
                )
                await asyncio.sleep(5)
            else:
                to_delete.append(message)
                self.go_to_page(int(message.content))

            with suppress(Exception):
                await self.ctx.channel.delete_messages(to_delete)

        elif isinstance(react, int):
            self.current += react
            if self.current < 0 or self.current > self.end:
                self.current -= react
        else:
            self.current = int(react)

    # https://discordpy.readthedocs.io/en/latest/api.html#discord.RawReactionActionEvent
    def check(self, payload):
        if payload.message_id != self.message.id:
            return False
        if payload.user_id != self.ctx.author.id:
            return False

        return str(payload.emoji) in self.reactions

    async def add_reactions(self):
        for reaction in self.reactions:
            with suppress(discord.Forbidden, discord.HTTPException):
                await self.message.add_reaction(reaction)

    async def paginator(self):
        with suppress(discord.HTTPException, discord.Forbidden, IndexError):
            self.message = await self.ctx.send(embed=self.pages[0])

        if len(self.pages) > 1:
            self.__tasks.append(self.loop.create_task(self.add_reactions()))

        while self.__is_running:
            with suppress(Exception):
                #creating tasks
                tasks = [
                    asyncio.ensure_future(
                        self.bot.wait_for("raw_reaction_add", check=self.check)
                    ),
                    asyncio.ensure_future(
                        self.bot.wait_for("raw_reaction_remove", check=self.check)
                    ),
                ]
                # do tasks until first completed
                # if not timeout the payload (reaciton) will went into done
                done, pending = await asyncio.wait(
                    tasks, timeout=self.timeout, return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()

                if len(done) == 0:
                    # Clear reactions once the timeout has elapsed
                    return await self.stop(timed_out=True)
                
                # get reaction
                payload = done.pop().result()
                reaction = self.reactions.get(str(payload.emoji))

                self.previous = self.current
                await self.controller(reaction)

                if self.previous == self.current:
                    continue

                with suppress(Exception):
                    await self.message.edit(embed=self.pages[self.current])

    async def stop(self, *, timed_out=False):
        with suppress(discord.HTTPException, discord.Forbidden):
            if timed_out:
                await self.message.clear_reactions()
            else:
                await self.message.delete()

        with suppress(Exception):
            self.__is_running = False
            for task in self.__tasks:
                task.cancel()
            self.__tasks.clear()

    async def start(self, ctx):
        """Start paginator session.

        Parameters
        -----------
        ctx: :class:`Context`
            The invocation context to use.
        """
        self.ctx = ctx
        self.bot = ctx.bot
        self.loop = ctx.bot.loop

        if isinstance(self.pages, discord.Embed):
            return await self.ctx.send(embed=self.pages)

        if isinstance(self.pages, list) and len(self.pages) == 1:
            return await self.ctx.send(embed=self.pages[0])

        if not isinstance(self.pages, (list, discord.Embed)):
            raise TypeError(
                "Can't paginate an instance of <class '%s'>."
                % self.pages.__class__.__name__
            )

        if len(self.pages) == 0:
            raise RuntimeError("Can't paginate an empty list.")

        self.end = float(len(self.pages) - 1)
        if self.compact is False:
            self.reactions["⏭"] = self.end
        self.__tasks.append(self.loop.create_task(self.paginator()))


class BaseSingleInstanceHandler():
    """
    Handles input of a single user.
    Call coro stop(reason) to stop the paginator completly
    Sends information to events:
    on_reaction_add(self, payload, user, emoji)
    on_reaction_remove(self, payload, user, emoji)
    on_message(self, message)
    on_message_edit(self, message)
    on_message_remove(self, message)
    on_error(self, error)
    on_stop(self, reason)
    before_event(self, future)
    after_event(self, future)
    on_start(self)
    """
    def __init__(
        self,
        timeout: float = None,
        embed: Union[list[discord.Embed], list[str]] = None,
        reactions_to_add: list[str] = [],
        remove_reactions: bool = True,
        enable_message: bool = True,
        enable_reaction_add: bool = True,
        enable_reaction_remove: bool = True,
        enable_message_edit: bool = False,
        enable_message_remove: bool = False,
    ) -> None:
        self.client = None
        self.loop = None
        self.ctx = None

        self.__tasks = []
        self._stop = False

        # customizable stuff
        self.message = None
        self.embed = embed
        self.reactions = reactions_to_add
        self.remove_reactions = remove_reactions
        self.timeout = timeout or 5*60
        self.enable_message: bool = enable_message
        self.enable_reaction_add: bool = enable_reaction_add
        self.enable_reaction_remove: bool = enable_reaction_remove
        self.enable_message_edit: bool = enable_message_edit
        self.enable_message_remove: bool = enable_message_remove

        self.numbers = [
            "0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣",
        ]
        self.convert_numbers = {
            value: num for num, value in enumerate(self.numbers)
        }
        self.letters = [
            '\N{regional indicator symbol letter a}',
            '\N{regional indicator symbol letter b}',
            '\N{regional indicator symbol letter c}',
            '\N{regional indicator symbol letter d}',
            '\N{regional indicator symbol letter e}',
            '\N{regional indicator symbol letter f}',
            '\N{regional indicator symbol letter g}',
            '\N{regional indicator symbol letter h}',
            '\N{regional indicator symbol letter i}',
        ]
        self.convert_letters = {
            value: letter+1 for letter, value in enumerate(self.letters)
        }

        self.convert_reacts = {}
        self.convert_reacts.update(self.convert_numbers)
        self.convert_reacts.update(self.convert_letters)

    async def send(self, ctx, page):
        #with suppress(discord.HTTPException, discord.Forbidden):
        try:
            if isinstance(page, discord.Embed):
                message = await ctx.send(embed=page)
            elif isinstance(page, str):
                message = await ctx.send(content=page)
        except:
            traceback.print_exc()
        return message

    async def start(self, ctx: Context):
        """
        Start MetaTikTakToe discord game.

        Parameters
        -----------
        ctx: :class:`Context`
            The invocation context to use.
        """
        self.ctx = ctx
        self.client = ctx.bot
        self.loop = ctx.bot.loop

        await self.on_start()
        if isinstance(self.embed, list):
            await self.send(ctx, self.embed[0])
        self.message = await ctx.send(self.embed)
        if self.reactions:
            for reaction in self.reactions:
                await self.message.add_reaction(reaction)

        self.__tasks.append(
            self.loop.create_task(self.main())
        )

    def payload_check(self, payload):
        # for reactions
        if (
            not payload.user_id == self.client.user.id
            and payload.user_id == self.ctx.author.id
            and payload.channel_id == self.ctx.channel.id
            and payload.message_id == self.message.id
        ):
            return True
        return False

    def message_check(self, message):
        # for messages
        return (
            not message.author.id == self.client.user.id
            and message.author.id == self.ctx.author.id
            and message.channel.id == self.ctx.channel.id
        )

    async def run_concurrent(self, *coros):
        """
        runs given coroutines concurrent until all are complete.
        *coros: coroutines
        """
        _, _ = await asyncio.wait(
            coros,
            timeout=self.timeout,
            return_when=asyncio.ALL_COMPLETED,
        )
        return

    async def main(self):
        
        while not self._stop:
            try:
                # creating tasks
                def discord_task(discord_event: str, check_func):
                    task = asyncio.ensure_future(
                        self.client.wait_for(
                            event=discord_event,
                            check=check_func,
                        )
                    )
                    task.set_name(discord_event)
                    return task

                tasks = []
                if self.enable_reaction_add:
                    tasks.append(discord_task("raw_reaction_add", check_func=self.payload_check))
                if self.enable_reaction_remove:
                    tasks.append(discord_task("raw_reaction_remove", check_func=self.payload_check))
                if self.enable_message:
                    tasks.append(discord_task("message", check_func=self.message_check))
                if self.enable_message_edit:
                    tasks.append(discord_task("message_edit", check_func=self.message_check))
                if self.enable_message_remove:
                    tasks.append(discord_task("message_remove", check_func=self.message_check))

                done, pending = await asyncio.wait(
                    tasks,
                    timeout=self.timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                # if stopped from outside
                if self._stop:
                    return

                for task in pending:
                    task.cancel()

                # timed out
                if len(done) == 0:
                    return await self.stop(reason=f"timeout")

                future = done.pop()
                await self._before_event(future=future)
                await self._call_event(future=future)
                await self._after_event(future=future)

            except Exception:
                await self.on_error(error=traceback.format_tb())
                traceback.print_exc()

    async def stop(self, reason=None, timeout=False):
        self._stop = True
        timed_out = True if reason == "timeout" else False
        await self.stop_paginator(timed_out=timed_out)
        await self.on_stop(reason=reason)

    async def _unpack_payload(self, future):
        payload = future.result()
        # get member from cache
        if payload.guild_id:
            user = self.ctx.guild.get_member(payload.user_id)
            # request member because member is not in cache
            if not user:
                user = await self.ctx.guild.fetch_member(payload.user_id)
        else:
            user = self.client.get_user(payload.user_id)
            if not user:
                user = await self.client.fetch_user(payload.user_id)
        return user, payload, str(payload.emoji)

    async def _call_event(self, future):
        name_and_type = future.get_name()
        if "reaction" in name_and_type:
            user, payload, emoji = await self._unpack_payload(future)

            if name_and_type == "raw_reaction_add":
                return await self.on_reaction_add(payload, user, emoji)
            elif name_and_type == "raw_reaction_remove":
                return await self.on_reaction_remove(payload, user, emoji)

        elif "message" in name_and_type:
            if "message" == name_and_type:
                return await self.on_message(future.result())
            elif "message_edit" == name_and_type:
                return await self.on_message_edit(future.result())
            elif "message_remove" == name_and_type:
                return await self.on_message_remove(future.result())

    async def stop_paginator(self, timed_out: bool = False):
        with suppress(discord.HTTPException, discord.Forbidden):
            if timed_out:
                await self.message.clear_reactions()
            else:
                await self.message.delete()

    def event(pass_future=True):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if pass_future:
                    return await func(*args, **kwargs)
                return func()
            return wrapper
        return decorator

    async def _before_stop(self, reason):
        pass

    async def _after_event(self, future):
        await self.after_event(future=future)

    @event(pass_future=True)
    async def after_event(self, future=None):
        pass

    async def _before_event(self, future):
        if (
            self.remove_reactions and "reaction_add" in future.get_name()
            and self.client.user.id != future.result().user_id
        ):
            async def reaction_remove_(future):
                user, _, emoji = await self._unpack_payload(future)
                await self.message.remove_reaction(emoji, user)
            return await self.run_concurrent(
                reaction_remove_(future),
                self.before_event(future),
            )
        await self.before_event(future=future)

    @event(pass_future=True)
    async def before_event(self, future=None):
        pass

    async def on_stop(self, reason: str):
        pass

    async def on_reaction_add(
        self,
        payload: discord.RawReactionActionEvent,
        user: Union[discord.Member, discord.User],
        emoji: str,
    ) -> None:
        pass

    async def on_reaction_remove(
        self,
        payload: discord.RawReactionActionEvent,
        user: Union[discord.Member, discord.User],
        emoji: str,
    ) -> None:
        pass

    async def on_message(self, message: discord.Message):
        pass

    async def on_message_edit(self, message: discord.Message):
        pass

    async def on_message_remove(self, message: discord.Message):
        pass

    async def on_error(self, error):
        pass

    async def on_start(self):
        pass

class BaseAdvancedPaginator(BaseSingleInstanceHandler):
    """Single Instance Handler with Paginator functionality"""
    def __init__(
        self,
        *,
        pages: Optional[Union[List[discord.Embed], discord.Embed, list[str]]] = None,
        compact: bool = False,
        timeout: float = 90.0,
        has_input: bool = True,
        reactions_to_add: list[str] = [],
        remove_reactions: bool = True,
        enable_message: bool = True,
        enable_reaction_add: bool = True,
        enable_reaction_remove: bool = True,
        enable_message_edit: bool = False,
        enable_message_remove: bool = False,
    ):

        # single instance + event stuff
        super().__init__(
            self,
            reactions_to_add=reactions_to_add,
            remove_reactions=remove_reactions,
            enable_message=enable_message,
            enable_reaction_add=enable_reaction_add,
            enable_reaction_remove=enable_reaction_remove,
            enable_message_edit=enable_message_edit,
            enable_message_remove=enable_message_remove,
        )

        self.__tasks = []
        self.pages = pages
        self.compact = compact
        self.timeout = timeout
        self.has_input = has_input

        self.current = 0
        self.previous = 0
        self.end = 0
        self.reactions = {
            "⏮": 0.0,
            "◀": -1,
            "⏹️": "stop",
            "▶": +1,
            "⏭": None,
        }

        if self.has_input is True:
            self.reactions["🔢"] = "input"

        if self.pages is not None:
            if len(self.pages) == 2:
                self.compact = True

        if self.compact is True:
            keys = ("⏮", "⏭", "🔢")
            for key in keys:
                try:
                    del self.reactions[key]
                except KeyError:
                    pass

    def go_to_page(self, number):
        if number > int(self.end):
            page = int(self.end)
        else:
            page = number - 1
        self.current = page

    async def controller(self, react):
        if react == "stop":
            await self.stop(reason="stop_react")

        elif react == "input":
            to_delete = []
            message = await self.ctx.send("What page do you want to go to?")
            to_delete.append(message)

            def check(m):
                if m.author.id != self.ctx.author.id:
                    return False
                if self.ctx.channel.id != m.channel.id:
                    return False
                if not m.content.isdigit():
                    return False
                return True

            try:
                message = await self.client.wait_for("message", check=check, timeout=30.0)
            except asyncio.TimeoutError:
                to_delete.append(
                    await self.ctx.send("You took too long to enter a number.")
                )
                await asyncio.sleep(5)
            else:
                to_delete.append(message)
                self.go_to_page(int(message.content))

            with suppress(Exception):
                await self.ctx.channel.delete_messages(to_delete)

        elif isinstance(react, int):
            self.current += react
            if self.current < 0 or self.current > self.end:
                self.current -= react
        else:
            self.current = int(react)

    async def do_paginating(self, future):
        if (
            "reaction" in future.get_name()
            and not (react := self.reactions.get(str(future.result().emoji), None))
            is None
        ):
            self.previous = self.current
            await self.controller(react)
            if not self.previous == self.current:
                with suppress(discord.HTTPException, discord.Forbidden):
                    if isinstance(self.pages[self.current], discord.Embed):
                        await self.message.edit(embed=self.pages[self.current])
                    elif isinstance(self.pages[self.current], str):
                        await self.message.edit(content=self.pages[self.current])
            return

    def concurrent(*coros, timeout=60):
        """
        decorator factory which returns a decorator which
        runs given coroutines concurrent with the decorated func (have to be a coro)
        until ALL_COMPLETETD. All coroutines get *args and **kwargs from decorated coro
        *coros: The coroutines which should be executed concurrent
        timeout: the timeout of running the coroutines
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                main_task = asyncio.ensure_future(func(*args, **kwargs))
                main_task.set_name("main_task")
                tasks = [main_task]
                for coro in coros:
                    tasks.append(
                        asyncio.ensure_future(coro(*args, **kwargs))
                    )
                return await asyncio.wait(
                    tasks,
                    timeout=timeout,
                    return_when=asyncio.ALL_COMPLETED,
                )
            return wrapper
        return decorator

    # (maybe) pagination and event dispatching are running concurrent
    @concurrent(do_paginating)
    async def _call_event(self, future):
        return await super()._call_event(future)

    async def start(self, ctx: Context):
        """
        Starts an Advanced Paginator session.

        Parameters
        -----------
        ctx: :class:`Context`
            The invocation context to use.
        """
        self.ctx = ctx
        self.client = ctx.bot
        self.loop = ctx.bot.loop

        if isinstance(self.pages, discord.Embed):
            await self.send(ctx, self.pages)
        # if isinstance(self.pages, discord.Embed):
        #     self.message = await self.ctx.send(embed=self.pages)

        # if not isinstance(self.pages, (list, discord.Embed)):
        #     raise TypeError(
        #         "Can't paginate an instance of <class '%s'>."
        #         % self.pages.__class__.__name__
        #     )

        if len(self.pages) == 0:
            raise RuntimeError("Can't paginate an empty list.")

        with suppress(discord.HTTPException, discord.Forbidden, IndexError):
            self.message = await self.send(ctx, self.pages[0])

        if self.reactions:
            for reaction in self.reactions:
                await self.message.add_reaction(reaction)

        self.end = float(len(self.pages) - 1)
        if self.compact is False:
            self.reactions["⏭"] = self.end
        
        await self.on_start()

        self.__tasks.append(
            self.loop.create_task(self.main())
        )

