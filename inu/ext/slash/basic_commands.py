import hikari
import lightbulb
import random



class Ping(SlashCommand):
    @property
    def name(self):
        return "ping"

    @property
    def description(self) -> str:
        return "checks if the bot is alive"

    @property
    def options(self) -> list:
        return []

    @property
    def enabled_guilds(self):
        return None

    async def callback(self, ctx) -> None:
        await ctx.respond("I am dead! Don't use me with fucking Slash Commands - than I am maybe alive")

class Test(slash_commands.SlashCommandGroup):

    @property
    def description(self) -> str:
        return "to test the library"


@Test.subcommand()
class echo(slash_commands.SlashSubCommand):
    name: str = "echo"
    description: str = "repeats your input text"
    to_echo: str = slash_commands.Option(description="Test")

    async def callback(self, ctx) -> None:
        return await ctx.respond(ctx.option_values.to_echo)
    
@Test.subcommand()
class echo2(slash_commands.SlashSubCommand):
    name: str = "twicee"
    description: str = "repeats your input text twice"
    to_echo: str = slash_commands.Option(description="Test")

    @property
    def enabled_guilds(self):
        return [538398443006066728]

    async def callback(self, ctx) -> None:
        await ctx.respond(ctx.option_values.to_echo)
        await ctx.respond(ctx.option_values.to_echo)
    


def load(bot):
    bot.add_slash_command(Ping)
    bot.add_slash_command(Test)
