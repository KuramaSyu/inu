import random
import re
import typing
from typing import (
    List,
    Sequence,
    Union,
    Optional,
    Mapping,
)
import hikari
import lightbulb
from lightbulb.help import get_command_signature, get_help_text
from matplotlib.colors import cnames

from core import Inu
from utils import Paginator

T_bot = typing.Union[lightbulb.Bot, Inu]

class CustomHelp(lightbulb.help.HelpCommand):
    def __init__(self, bot: T_bot):
        self.bot = bot
        
        super().__init__(bot=bot)


class Help(lightbulb.Plugin):
    def __init__(self, bot: T_bot):
        super().__init__(name="Help")
        self.bot = bot
        self.cmds_per_list: int = 5
        self.bot.remove_command("help")

    @lightbulb.command()
    async def help(self, ctx: lightbulb.Context, query: Optional[str] = None):
        """
        Sends help for all or a given query
        Arguments:
        [Optional] query: the thing you want to search for
        """
        cmds = self.search(ctx, query)
        await self.create_help(ctx, cmds)

    def search(
        self,
        ctx: lightbulb.Context, 
        query: Optional[str] = None
    ) -> List[lightbulb.Command]:
        cmds: Sequence[lightbulb.Command] = []
        for cmd in self.bot.walk_commands():
            if query == None or query in cmd.qualified_name:
                cmds.append(cmd)
        if not cmds and query and len(query) > 1:
            return self.search(ctx, query[:-1])
        else:
            return cmds
        
    
    async def create_help(self, ctx, cmds: List[lightbulb.Command]):
        filtered_cmds = self.filter_hidden(cmds)
        if not filtered_cmds:
            return
        embeds = await self.create_embed_from(filtered_cmds, ctx)
        pag = Paginator(page_s=embeds)
        await pag.start(ctx)
        
    def filter_hidden(
        self,
        cmds: Sequence[lightbulb.Command]
    ) -> Optional[Sequence[lightbulb.Command]]:
        cmds_filtered = []
        for cmd in cmds:
            if cmd.hidden:
                continue
            cmds_filtered.append(cmd)
        return cmds_filtered

    async def create_embed_from(
        self,
        cmds: Sequence[lightbulb.Command],
        ctx: lightbulb.Context,
    ) -> Sequence[hikari.Embed]:
        pages = []
        
        for i, cmd in enumerate(cmds):
            if i % self.cmds_per_list == 0:
                pages.append([])
            command_entry = "<....> needed\n[....] optional\n\n"
            desc = get_help_text(cmd)
            signature = self.get_command_signature(cmd, ctx)
            subcommand = ""
            if isinstance(cmd, lightbulb.commands.Group):
                subcommand = "Sub commands: " + ", ".join([c.name for c in cmd.walk_commands()]) + "\n"
            command_entry += (
                f"{'•' if not subcommand else '⋗'} **{cmd.qualified_name}**\n"
                f"{subcommand}```\n{signature}\n```\n{desc}\n\n"
            )
            pages[-1].append(command_entry)
        
        embeds = []
        colors = [  "orange", "darkorange", "firebrick", "yellowgreen", "limegreen", "mediumturquoise",
                    "teal", "deepskyblue", "steelblue", "royalblue", "midnightblue",
                    "slateblue", "blueviolet", "darkviolet", "purple", "crimson"
        ]
        def random_color() -> str:
            return cnames[random.choice(colors)]

        for page in pages:
            embed = hikari.Embed()
            embed.title = "Help"
            embed.description = ""
            embed.color = hikari.Color.from_hex_code(random_color())
            for descr in page:
                embed.description += f"\n{descr}"
            embeds.append(embed)

        return embeds

    def remove_defaults(self, cmd_signature: str) -> str:
        start = cmd_signature.find("=")
        if start == -1:
            return cmd_signature
        end = []
        end.append(cmd_signature.find(">", start))
        end.append(cmd_signature.find("]", start))
        while -1 in end:
            end.remove(-1)

        to_remove = cmd_signature[start:min(end)]
        cmd_signature = re.sub(to_remove, '', cmd_signature)

        if "=" in cmd_signature:
            cmd_signature = self.remove_defaults(cmd_signature)
        return cmd_signature

    def get_command_signature(self, command: lightbulb.Command, ctx: lightbulb.Context):
        aliases = ", ".join(command.aliases)
        #cmd_invoke = f"{command.name}({aliases})" if command.aliases else command.name
        cmd_invoke = f"{command.name}"
        full_invoke = command.qualified_name.replace(command.name, "")
        cmd_sign = self.remove_defaults(get_command_signature(command))

        signature = f"{ctx.prefix}{cmd_sign}" #{full_invoke} ..
        signature += f"\nequal to '{cmd_invoke}': {aliases}" if aliases else ''
        return signature

                    







def load(bot: T_bot):
    bot.add_plugin(Help(bot))

# def unload(bot):
#     bot.remove_plugin("Help")