import asyncio
import typing
from typing import (
    Any,
    Callable,
    Optional,
    TypeVar,
    Union,
    List,
    Final
)
import traceback
from contextlib import suppress
import logging

import hikari
from hikari.embeds import Embed
from hikari.messages import Message
from hikari.impl import ActionRowBuilder
from hikari import ButtonStyle, InteractionCreateEvent, MessageCreateEvent
import lightbulb
from lightbulb.context import Context

from core import Inu
from utils import build_logger



__all__: Final[List[str]] = ["BasePaginator"]
_Sendable = Union[Embed, str]
T = TypeVar("T")

class BasePaginator():
    def __init__(
        self,
        page_s: Union[List[Embed], List[str]],
        convert_to_embed = True,
        timeout: int = 120,
    ):
        self.log = logging.getLogger(name=None)
        self.log.debug("__init__ pag")
        self.pages: Union[List[Embed], List[str]] = page_s
        self.bot: lightbulb.Bot
        self.ctx: Context
        self._task: asyncio.Task
        self._message: Message 
        self.components: List[ActionRowBuilder]

        self.timeout = timeout
        self._stop = False
        self._position: int

    def interaction_pred(self, event: InteractionCreateEvent):
        self.log.debug("in interactiion check")
        i = event.interaction
        return (
            i.user.id == self.ctx.author.id
            and i.message.id == self._message.id
        )
    def message_pred(self, event: MessageCreateEvent):
        self.log.debug("message check")
        msg = event.message
        return (
            msg.channel_id == self.ctx.channel_id
            and self.ctx.author.id == msg.author.id
        )

    def build_default_components(self) -> ActionRowBuilder:

        def button_factory( 
            label: str = "",
            style = ButtonStyle.SECONDARY,
            custom_id: Optional[str] = None,
            emoji: Optional[str] = None,
            action_row_builder: ActionRowBuilder = ActionRowBuilder()
        ) -> ActionRowBuilder:
            if not custom_id:
                custom_id = label
            if not emoji:
                btn = (
                    action_row_builder
                    .add_button(style, custom_id)
                    .set_label(label)
                    .add_to_container()
                )
            else:
                btn = (
                    action_row_builder
                    .add_button(style, custom_id)
                    .set_emoji(emoji)
                    .add_to_container()
                )
            return btn

        action_row = button_factory(custom_id="first", emoji="⏮")
        button_factory(custom_id="previous", emoji="⏪", action_row_builder=action_row)
        button_factory(custom_id="stop", emoji="⏹", action_row_builder=action_row, style=ButtonStyle.DANGER)
        button_factory(custom_id="next", emoji="⏩", action_row_builder=action_row)
        button_factory(custom_id="last", emoji="⏭", action_row_builder=action_row)

        return action_row



    async def send(self, content: _Sendable):
        with suppress():
            if isinstance(content, str):
                self._message = await self._message.edit(
                    content=content
                )
            elif isinstance(content, Embed):
                self._message = await self._message.edit(
                    embed=content
                )
            else:
                raise TypeError(f"<content> can't be an isntance of {type(content).__name__}")

    async def start(self, ctx: Context) -> None:
        self.log.debug("start pag")
        print("start")
        self.ctx = ctx
        self.bot= ctx.bot
        if len(self.pages) <= 1:
            raise RuntimeError("<pages> must have minimum 1 item")
        if isinstance(self.pages[-1], Embed):
            self._message = await ctx.respond(
                embed=self.pages[-1],
                component=self.build_default_components()
            )
        else:
            self._message = await ctx.respond(content=self.pages[-1])
        
        if len(self.pages) == 1:
            return
        self._position = 0
        self._task = asyncio.create_task(self.pagination_loop())
        


    async def pagination_loop(self):
        if self.timeout > int(60*15):
            raise RuntimeError("<timeout> has a max time of 15 min")
        def create_event(event, predicate: Callable):
            return self.bot.wait_for(
                event,
                timeout=self.timeout,
                predicate=predicate
            )

        while not self._stop:
            try:
                events = [
                    create_event(InteractionCreateEvent, self.interaction_pred),
                    create_event(MessageCreateEvent, self.message_pred),
                ]
                self.log.debug("done, pending")
                done, pending = await asyncio.wait(
                    [asyncio.create_task(task) for task in events],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                self._stop = True
                return
            self.log.debug("make event done")
            try:
                event = done.pop().result()
            except Exception as e:
                self.log.info(e)
            for e in pending:
                e.cancel()

            self.log.debug("dispatch event")
            await self.dispatch_event(event)
            
    async def dispatch_event(self, event: typing.Any):
        if isinstance(event, InteractionCreateEvent):
            self.log.debug("paginate")
            await self.paginate(event)
            await self.on_interaction(event.interaction)
            self.log.debug("leave displatcher")


    async def paginate(self, event):
        self.log.debug("in paginate")
        try:
            id = event.interaction.custom_id
        except Exception as e:
            self.log.error(e)
        self.log.debug("after id")
        last_position = self._position
        if id == "first":
            self._position = 0
        elif id == "previous":
            if self._position == 0:
                return
            self._position -= 1
        elif id == "stop":
            pass
        elif id == "next":
            if self._position == (len(self.pages)-1):
                return
            self._position += 1
        elif id == "last":
            self._position = len(self.pages)-1

        if last_position != self._position:
            self.log.debug("pos update")
            await self._update_position()
        self.log.debug("leave pagination")

    async def _update_position(self):
        await self.send(content=self.pages[self._position])

    async def on_interaction(self, interaction):
        pass

            
            
