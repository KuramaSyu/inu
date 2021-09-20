"""
MIT License

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
from typing import List, Union, Optional
from contextlib import suppress
import re

import discord
from discord.ext.commands.errors import BadArgument


class Connect4:
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

    def __init__(self):
        self.last_ctx = None
        self.client = client

        self.board = ['⬛' for _ in range(int(8*8))]
        self.winning_conditions = []
        self.gameOver = True
        self.player1 = int()
        self.player2 = int()
        self.turn = 'starting game...'
        self.board_message = ''
        self.mark = ''
        self.turn_count = int(0)
        self.error_message = ''
        self.board_message_id = int()
        self.game_board = ''
        self.board_title = '——————————Connect 4——————————'
        self.board_description = 'Game in progress'
        self.value1_title = f'Turn {self.turn_count}'
        self.board_footer = f'{self.turn}'
        self.value2_title = 'Log'
        self.value2 = '———————\n'
        self.mark1 = ''
        self.mark2 = ''
        self.should_logic_run = None
        self.old_player1 = None
        self.old_player2 = None
        self.old_board_message_id = None
        self.inu = None

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



class MusicHistoryPaginator(Paginator):
    '''
    Paginator for music history.
    New feature: Adding songs with the number symbol
    '''
    async def controller(self, react):
        if react == "stop":
            await self.stop()

        elif react == "input":
            to_delete = []
            message = await self.ctx.send("Which song(s) should I add for you ?")
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
                    await self.ctx.send("You took too long to enter your wished songs :/")
                )
                await asyncio.sleep(5)
            else:
                to_delete.append(message)
                number_list = self._get_numbers(message.content)

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
    

    async def _get_numbers(self, string: str) -> List:
        '''
        returns a list with all numbers form a string
        '''
        string = re.sub(',', ' ', string) # make comma to space
        string = re.sub('  ', ' ', string) # make double space to space
        li = list(string.split(" "))
        for e in li:
            for l in e:
                if l not in '1234567890':
                    raise BadArgument(f'"{l}" is not a number')
        # convert list to int's
        number_list = []
        for e in li:
            try:
                number_list.append(int(e))
            except:pass
        return number_list

    
    async def _add_songs(self, list_) -> None:
        inu_music = self.bot.get_cog('InuLavalink')
        if not inu_music:
            print('no instance of InuLavalink found')
            return
        for url in list_:
            inu_music.play(url)

        pass
