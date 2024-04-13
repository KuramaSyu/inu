from hikari import Embed
import lightbulb
from lightbulb import commands, context

from core import getLogger, BotResponseError
from utils import Urban, Paginator, Colors


log = getLogger(__name__)
plugin = lightbulb.Plugin("Dictionary", "Extends the commands with urban commands")



@plugin.command
@lightbulb.option("word", "What do you want to search?")
@lightbulb.command(
    "urban", 
    "Search a word in the urban (city) dictionary", 
    aliases=["urban-dictionary"],
    auto_defer=True,
)
@lightbulb.implements(commands.SlashCommand, commands.PrefixCommand)
async def urban_search(ctx: context.Context):
    try:
        pag = Paginator(
            page_s=[
                Embed(
                    description=(
                        f"**Description for [{ctx.options.word}]({d['permalink']}):**\n"
                        f"{d['definition'].replace('[', '').replace(']', '')}\n\n"
                    ),
                    color=Colors.random_color(),
                )
                .add_field(
                    "Example",
                    f"{d['example'].replace('[', '').replace(']', '')}" or "---",
                    inline=False,
                )
                .set_footer(
                    text=f"{d['thumbs_up']}👍 | {d['thumbs_down']}👎",
                )
                .set_thumbnail(
                    "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f0/Urban_Dictionary_logo.svg/512px-Urban_Dictionary_logo.svg.png"
                )
                for d in await Urban.fetch(ctx.options.word)
            ],
            compact=True,
            timeout=120,
        )
        await pag.start(ctx)
    except BotResponseError as e:
        await ctx.respond(e.bot_message)



def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)



