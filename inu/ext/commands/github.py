import asyncio
from typing import *
from datetime import datetime
import hikari
import lightbulb

from fuzzywuzzy import fuzz
from hikari import (
    Embed,
    ResponseType, 
    TextInputStyle,
    ApplicationContextType
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import commands, context, SlashCommand, invoke, Loader


from utils import (
    Colors, 
    Human, 
    Paginator, 
    crumble,
    GitHubAPI,
    Commit,
)
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger,
    InuContext,
    get_context
)

log = getLogger(__name__)

loader = lightbulb.Loader()
bot: Inu

@loader.command
class ChangeLog(
    SlashCommand,
    name="change-log",
    description="Last changes of the bot",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL]
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        github = GitHubAPI.INU_REPO()
        commits = await github.fetch_commits()
        embeds: List[Embed] = [
            Embed(title="Last Changes", color=Colors.pastel_color())
        ]
        for commit in commits:
            if not commit.has_keywords(commit.DEFAULT_KEYWORDS):
                continue
            if len(embeds[-1].fields) >= 24:
                embeds.append(Embed(title="Last Changes", color=Colors.pastel_color()))
            value = f"{commit.description}\n<t:{commit.date.timestamp():.0f}:f>"
            embeds[-1].add_field(
                name=commit.title,
                value=value,
            )
        embeds = [embed for embed in embeds if embed.fields]
        if not embeds:
            return await ctx.respond("No changes found", ephemeral=True)
        paginator = Paginator(page_s=embeds)
        await paginator.start(ctx)

