from typing import *
from abc import ABC, abstractmethod

from hikari import Message, Embed, ComponentInteraction, CommandInteraction, PartialWebhook, SnowflakeishOr, Snowflakeish
from hikari.api import Response
from hikari.impl import MessageActionRowBuilder

class ResponseProxy(ABC):
    @abstractmethod
    async def edit(
        self,
        content: str | None,
        *,
        embeds: List[Embed] | None = None,
        components: List[MessageActionRowBuilder] | None = None,

    ) -> None:
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
        content: str | None,
        *,
        embeds: List[Embed] | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> None:
        msg = await self._interaction.edit_initial_response(
            content=content,
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
        content: str | None,
        *,
        embeds: List[Embed] | None = None,
        components: List[MessageActionRowBuilder] | None = None,
    ) -> None:
        await self._interaction.edit_message(
            self._message, content,
            embeds=embeds,
            components=components,
        )

    async def delete(self) -> None:
        await self._interaction.delete_message(self._message)

    async def message(self) -> Message:
        if isinstance(self._message, Message):
            return self._message
        return await self._interaction.fetch_message(self._message)
