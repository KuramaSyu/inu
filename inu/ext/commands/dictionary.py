from hikari import Embed, ApplicationContextType
import lightbulb
from lightbulb import commands, context, SlashCommand, invoke, Loader

from core import getLogger, BotResponseError, Inu, InuContext
from utils import Urban, Paginator, Colors


log = getLogger(__name__)
loader = lightbulb.Loader()

@loader.error_handler
async def handler(exc: lightbulb.exceptions.ExecutionPipelineFailedException) -> bool:
    if isinstance(exc.causes[0], BotResponseError):
        await exc.context.respond(exc.causes[0].bot_message)
        return True
    return False

@loader.command
class UrbanDictionaryCommand(
    SlashCommand,
    name="urban",
    description="Search a word in the urban (city) dictionary",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    word = lightbulb.string("word", "What do you want to search?")

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await ctx.defer()
        pag = Paginator(
            page_s=[
                Embed(
                    description=(
                        f"**Description for [{self.word}]({d['permalink']}):**\n"
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
                for d in await Urban.fetch(self.word)
            ],
            compact=True,
            timeout=120,
        )
        await pag.start(ctx)



