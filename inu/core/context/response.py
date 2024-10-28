import asyncio

import hikari
from hikari import Embed, ComponentInteraction, CommandInteraction
from hikari.impl import MessageActionRowBuilder
from datetime import timedelta

from . import Response



class InteractionResponse(Response):
    def __init__(self, interaction: ComponentInteraction) -> None:
        self.interaction: ComponentInteraction = interaction
        self._deferred: bool = False
        self._responded: bool = False
        self._response_lock: asyncio.Lock = asyncio.Lock()
    
    async def defer(self, ephemeral: bool = False, update: bool = False):
        await self._response_lock.acquire()
        
        if self._responded or self._deferred:
            return
        
        flags = hikari.MessageFlag.NONE
        if ephemeral:
            flags = hikari.MessageFlag.EPHEMERAL
            
        match update:
            case True:
                response_type = hikari.ResponseType.DEFERRED_MESSAGE_UPDATE
            case False:
                response_type = hikari.ResponseType.DEFERRED_MESSAGE_CREATE
                
        await self.interaction.create_initial_response(response_type, flags=flags)
        self._response_lock.release()
        
    async def respond(
        self,
        embeds: list[Embed] | None = None,
        content: str | None = None,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: list[MessageActionRowBuilder] | None = None,
    ):
        pass