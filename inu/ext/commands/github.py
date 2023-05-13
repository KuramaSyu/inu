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
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import commands, context


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

plugin = lightbulb.Plugin("Name", "Description")
bot: Inu

@plugin.command
@lightbulb.command("change-log", "Last changes of the bot")
@lightbulb.implements(commands.SlashCommand, commands.PrefixCommand)
async def change_log(_ctx: context.Context):
    ctx = get_context(_ctx.event)
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
    

        





def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

