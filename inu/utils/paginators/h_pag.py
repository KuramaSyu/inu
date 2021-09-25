import asyncio
import typing
from typing import (
    Any,
    Callable,
    Optional,
    Sequence,
    TypeVar,
    Union,
    List,
    Final,
    Dict
)
import traceback
from contextlib import suppress
import logging

import hikari
from hikari.embeds import Embed
from hikari.messages import Message
from hikari.impl import ActionRowBuilder
from hikari import ButtonStyle, ComponentInteraction, InteractionCreateEvent, MessageCreateEvent, ResponseType
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
        page_s: Union[Sequence[Embed], Sequence[str]],
        convert_to_embed = True,
        timeout: int = 120,
    ):
        self.pages: Union[Sequence[Embed], Sequence[str]] = page_s
        self.bot: lightbulb.Bot
        self.ctx: Context
        self._task: asyncio.Task
        self._message: Message
        self.components: List[ActionRowBuilder]

        self.timeout = timeout
        self._stop = False
        self._position: int

    def interaction_pred(self, event: InteractionCreateEvent):
        if not isinstance((i := event.interaction), ComponentInteraction):
            return False
        return (
            i.user.id == self.ctx.author.id
            and i.message.id == self._message.id
        )

    def message_pred(self, event: MessageCreateEvent):
        msg = event.message
        return (
            msg.channel_id == self.ctx.channel_id
            and self.ctx.author.id == msg.author.id
        )

    def build_default_components(self) -> ActionRowBuilder:

        def button_factory( 
            disable_when_index_is: Union[Callable[[Optional[int]], bool]] = (lambda x: False),
            label: str = "",
            style = ButtonStyle.SECONDARY,
            custom_id: Optional[str] = None,
            emoji: Optional[str] = None,
            action_row_builder: ActionRowBuilder = ActionRowBuilder(),
            
        ) -> ActionRowBuilder:
            state: bool = disable_when_index_is(self._position)
            if not custom_id:
                custom_id = label
            if not emoji:
                btn = (
                    action_row_builder
                    .add_button(style, custom_id)
                    .set_is_disabled(state)
                    .set_label(label)
                    .add_to_container()
                )
            else:
                btn = (
                    action_row_builder
                    .add_button(style, custom_id)
                    .set_is_disabled(state)
                    .set_emoji(emoji)
                    .add_to_container()
                )
            return btn
        action_row = button_factory(
            custom_id="first", 
            emoji="⏮", 
            disable_when_index_is=lambda p: p == 0
        )
        button_factory(
            custom_id="previous",
            emoji="⏪",
            action_row_builder=action_row,
            disable_when_index_is=lambda p: p == 0,
        )
        button_factory(
            custom_id="stop",
            emoji="⏹",
            action_row_builder=action_row,
            style=ButtonStyle.DANGER,
        )
        button_factory(
            custom_id="next",
            emoji="⏩",
            action_row_builder=action_row,
            disable_when_index_is=lambda p: p == len(self.pages)-1,
        )
        button_factory(
            custom_id="last",
            emoji="⏭",
            action_row_builder=action_row,
            disable_when_index_is=lambda p: p == len(self.pages)-1,
        )

        return action_row



    async def send(self, content: _Sendable, interaction: Optional[ComponentInteraction] = None):
        try:
            kwargs: Dict[str, Any] = {}
            if interaction:
                update_message = interaction.create_initial_response
                kwargs["response_type"] = hikari.ResponseType.MESSAGE_UPDATE
                kwargs["component"] = self.build_default_components()
            else:
                update_message = self._message.edit
            if isinstance(content, str):
                kwargs["content"] = content
                await update_message(**kwargs)
            elif isinstance(content, Embed):
                kwargs["embed"] = content
                await update_message(**kwargs)
            else:
                raise TypeError(f"<content> can't be an isntance of {type(content).__name__}")
        except Exception as e:
            print(e)

    async def stop(self):
        self._stop = True
        await self._message.edit(component=None)

    async def start(self, ctx: Context) -> None:
        self.ctx = ctx
        self.bot = ctx.bot
        if len(self.pages) < 1:
            raise RuntimeError("<pages> must have minimum 1 item")
        elif len(self.pages) == 1:
            if isinstance(self.pages[0], Embed):
                self._message = await ctx.respond(
                    embed=self.pages[0],
                )
            else:
                self._message = await ctx.respond(
                    content=self.pages[0],
                )
            return
        self._position = 0
        if isinstance(self.pages[0], Embed):
            self._message = await ctx.respond(
                embed=self.pages[0],
                component=self.build_default_components()
            )
        else:
            self._message = await ctx.respond(
                content=self.pages[-1],
                component=self.build_default_components()
            )
        
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
                done, pending = await asyncio.wait(
                    [asyncio.create_task(task) for task in events],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                self._stop = True
                return
            # maybe called from outside
            if self._stop:
                return
            try:
                event = done.pop().result()
            except Exception:
                pass
            for e in pending:
                e.cancel()
            await self.dispatch_event(event)
            
    async def dispatch_event(self, event: typing.Any):
        if isinstance(event, InteractionCreateEvent):
            await self.paginate(event)

    async def paginate(self, event):
        id = event.interaction.custom_id
        last_position = self._position

        if id == "first":
            self._position = 0
        elif id == "previous":
            if self._position == 0:
                return
            self._position -= 1
        elif id == "stop":
            await self.stop()
        elif id == "next":
            if self._position == (len(self.pages)-1):
                return
            self._position += 1
        elif id == "last":
            self._position = len(self.pages)-1

        if last_position != self._position:
            await self._update_position(interaction=event.interaction)

    async def _update_position(self, interaction: ComponentInteraction):
        await self.send(content=self.pages[self._position], interaction=interaction)

    async def on_interaction(self, interaction):
        pass

            
            
