import typing
from typing import *
import asyncio
import logging
from datetime import datetime

import hikari
from hikari import ButtonStyle
from hikari.impl.special_endpoints import MessageActionRowBuilder, LinkButtonBuilder
import lightbulb
from lightbulb import Context, SlashCommand, invoke

from utils import Colors, Human, Paginator, crumble
from core import getLogger, Inu, InuContext

log = getLogger(__name__)

loader = lightbulb.Loader()
bot = Inu.instance

# async def voice_channel_autocomplete(ctx: lightbulb.AutocompleteContext) -> List[str]:
#     vcs = []
#     guild = ctx.interaction.get_guild()
#     if not guild:
#         return []
#     for ch in guild.get_channels().values():
#         if not isinstance(ch, hikari.GuildVoiceChannel):
#             continue
#         if permissions_in(ch, ctx.interaction.member) & hikari.Permissions.CONNECT:
#             vcs.append(f"{ch.id} | {ch.name}")
#     return vcs[:24]

@loader.command
class MoveAllCommand(
    SlashCommand,
    name="move-all",
    description="moves all members from a current voice channel into another",
    dm_enabled=False,
    hooks=[
        lightbulb.prefab.bot_has_permissions(hikari.Permissions.MOVE_MEMBERS),
        lightbulb.prefab.has_permissions(hikari.Permissions.MOVE_MEMBERS),
    ],
):
    voice_channel = lightbulb.channel(
        "voice-channel",
        "the voice channel where you want to move to",
        channel_types=[hikari.ChannelType.GUILD_VOICE],
    )
    from_voice_channel = lightbulb.channel(
        "from-voice-channel",
        "the voice channel where move people of",
        channel_types=[hikari.ChannelType.GUILD_VOICE],
        default=None,
    )

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext) -> None:
        assert ctx.guild_id
        target_channel = self.voice_channel
        if not target_channel.type == hikari.ChannelType.GUILD_VOICE:
            await ctx.respond(f"{target_channel} is not a voice channel", flags=hikari.MessageFlag.EPHEMERAL)
            return None

        if not self.from_voice_channel:
            member = ctx.member
            assert member
            states = ctx.bot.cache.get_voice_states_view_for_guild(ctx.guild_id)
            voice_state = [state for state in states.values() if state.user_id == member.id]

            if not voice_state:
                await ctx.respond(f"{member.display_name} needs to be in a voice channel")
                return None

            channel_id = voice_state[0].channel_id
            user_ids = [state.user_id for state in states.values() if state.channel_id == channel_id]
        else:
            user_ids = [
                state.user_id for state in ctx.bot.cache.get_voice_states_view_for_guild(ctx.guild_id).values()
                if state.channel_id == self.from_voice_channel.id
            ]
        
        tasks = [
            asyncio.create_task(
                ctx.bot.rest.edit_member(
                    guild=ctx.guild_id, 
                    user=user_id, 
                    voice_channel=target_channel.id
                )
            )
            for user_id in user_ids
        ]
        await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
        await ctx.respond(
            f"Moved {Human.list_([f'<@{user_id}>' for user_id in user_ids], with_a_or_an=False)} to `{target_channel.name}`"
        )

