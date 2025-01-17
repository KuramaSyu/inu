from typing import *
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import asyncio
from contextlib import suppress

from hikari import Message, Embed, ComponentInteraction, CommandInteraction, PartialWebhook, SnowflakeishOr, Snowflakeish, NotFoundError
from hikari.api import Response
from hikari.impl import MessageActionRowBuilder
from pytz import utc

class ResponseProxy(ABC):
    created_at: datetime

    def __init__(self) -> None:
        self.created_at: datetime = datetime.now(utc)
    @abstractmethod
    async def edit(
        self,
        content: str | None = None,
        embed: Embed | None = None,
        embeds: List[Embed] | None = None,
        component: MessageActionRowBuilder | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> Message:
        pass

    @abstractmethod
    async def delete(self) -> None:
        pass

    @abstractmethod
    async def message(self) -> Message:
        pass

    async def delete_after(self, delay: timedelta) -> None:
        """Schedule message deletion after specified delay"""
        await asyncio.sleep(delay.total_seconds())
        with suppress(NotFoundError):
            await self.delete()


class RestResponseProxy(ResponseProxy):
    def __init__(self, message: Message) -> None:
        super().__init__()
        self._message: Message = message

    async def edit(
        self,
        content: str | None = None,
        embed: Embed | None = None,
        embeds: List[Embed] | None = None,
        component: MessageActionRowBuilder | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> Message:
        embeds = embeds or [embed] if embed else []
        components = components or [component] if component else []
        
        return await self._message.edit(
            content,
            embeds=embeds,
            components=components,
        )

    async def delete(self) -> None:
        await self._message.delete()

    async def message(self) -> Message:
        return self._message


class InitialResponseProxy(ResponseProxy):
    def __init__(
        self,
        interaction: ComponentInteraction | CommandInteraction,
    ) -> None:
        super().__init__()
        self._interaction: ComponentInteraction | CommandInteraction = interaction
    
    async def edit(
        self,
        content: str | None = None,
        embed: Embed | None = None,
        embeds: List[Embed] | None = None,
        component: MessageActionRowBuilder | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> Message:
        embeds = embeds or [embed] if embed else []
        components = components or [component] if component else []
        
        return await self._interaction.edit_initial_response(
            content,
            embeds=embeds,
            components=components,
        )

    async def delete(self) -> None:
        await self._interaction.delete_initial_response()

    async def message(self) -> Message:
        return await self._interaction.fetch_initial_response()


class WebhookProxy(ResponseProxy):
    def __init__(
        self,
        message: SnowflakeishOr[Message],
        interaction: ComponentInteraction | CommandInteraction,
    ) -> None:
        super().__init__()
        self._message: SnowflakeishOr[Message] = message
        self._interaction: ComponentInteraction | CommandInteraction = interaction

    async def edit(
        self,
        content: str | None = None,
        embed: Embed | None = None,
        embeds: List[Embed] | None = None,
        component: MessageActionRowBuilder | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> Message:
        embeds = embeds or [embed] if embed else []
        components = components or [component] if component else []
        
        return await self._interaction.edit_message(
            self._message, 
            content,
            embeds=embeds,
            components=components,
        )

    async def delete(self) -> None:
        await self._interaction.delete_message(self._message)

    async def message(self) -> Message:
        if isinstance(self._message, Message):
            return self._message
        return await self._interaction.fetch_message(self._message)
