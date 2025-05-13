import typing
from typing import *
import asyncio
import logging

import hikari
from hikari import ApplicationContextType

import lightbulb
from lightbulb import Context, SlashCommand, invoke

from utils import InvokationStats, Colors
from core import getLogger, Inu, InuContext

log = getLogger(__name__)

loader = lightbulb.Loader()
bot = Inu.instance


async def send_formated_json(ctx: InuContext, json_: dict):
    embed = hikari.Embed(title="Command usage", description="")
    embed.color = Colors.random_color()
    cmd_list = []
    total_cmds = 0

    for command, value in json_.items():
        cmd_list.append({command: value})
    cmd_list.sort(key=lambda d: [*d.values()][0], reverse=True)
    for i, d in enumerate(cmd_list):
        if i % 10 == 0:
            embed.add_field(f"---- {'top ' if i in [0,10,20] else ''}{i+10} ----", value="", inline=True)
        for command, value in d.items():
            embed._fields[-1].value += f"**{command}**: {value}x\n"  # type: ignore
            total_cmds += value

    embed.description = f"Total used commands: {total_cmds}"
    await ctx.respond(embed=embed)

stats_group = lightbulb.Group("stats", "Command invocation infos", contexts=[ApplicationContextType.GUILD])

@stats_group.register
class GuildStatsCommand(
    SlashCommand,
    name="guild", 
    description="the command stats for this guild",
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        assert ctx.guild_id is not None
        json_ = await InvokationStats.fetch_json(ctx.guild_id)
        if not json_:
            return await ctx.respond("No stats available")
        await send_formated_json(ctx, json_)

@stats_group.register
class GlobalStatsCommand(
    SlashCommand,
    name="global",
    description="the command stats for all guilds where I am in",
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        json_ = await InvokationStats.fetch_global_json()
        if not json_:
            return await ctx.respond("No stats available")
        await send_formated_json(ctx, json_)

loader.command(stats_group)
