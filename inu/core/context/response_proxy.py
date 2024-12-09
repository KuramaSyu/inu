from typing import *
from abc import ABC, abstractmethod

from hikari import Message, Embed, ComponentInteraction, CommandInteraction, PartialWebhook, SnowflakeishOr, Snowflakeish
from hikari.api import Response
from hikari.impl import MessageActionRowBuilder

class ResponseProxy(ABC):
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


class InitialResponseProxy(ResponseProxy):
    def __init__(
        self,
        interaction: ComponentInteraction | CommandInteraction,
    ) -> None:
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
