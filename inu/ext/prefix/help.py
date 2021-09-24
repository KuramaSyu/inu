from optparse import Option
from click import command
import hikari
import lightbulb
import typing
from typing import (
    List,
    Sequence,
    Union,
    Optional,
    Mapping,
)

from core import Inu

T_bot = typing.Union[lightbulb.Bot, Inu]

class Help(lightbulb.help.HelpCommand):
    def __init__(self, bot: T_bot):
        self.bot = bot
        self.cmds_per_list: int = 8
        super().__init__(bot=bot)

    @lightbulb.command()
    async def help(self, ctx: lightbulb.Context, query: Optional[str] = None):
        pass

    async def help_all(self, ctx: lightbulb.Context):
        cmds: Sequence[lightbulb.Command] = []
        for cmd in self.bot.walk_commands():
            cmds.append(cmd)
        if not cmds:
            return
        filtered_cmds = self.filter_hidden(cmds)
        if not filtered_cmds:
            return
        embeds = await self.create_embed_from(filtered_cmds)
        await ctx.respond(embed=embeds[-1])
        
    def filter_hidden(self, 
    cmds: Sequence[lightbulb.Command]
    ) -> Sequence[Optional[lightbulb.Command]]:
        cmds_filtered = []
        for cmd in cmds:
            if cmd.hidden:
                continue
            cmds_filtered.append(cmd)
        return cmds_filtered

    async def create_embed_from(
        self,
        cmds: Sequence[lightbulb.Command]
    ) -> Sequence[hikari.Embed]:
        pages = []
        for i, cmd in enumerate(cmds):
            if i % self.cmds_per_list == 0:
                pages.append([])
            cmd_descr = (
                f"{cmd.qualified_name}\n"
                f"```\n{cmd.arg_details}\n```"
            )
            pages[-1].append(cmd_descr)
        
        embeds = []
        for page in pages:
            embed = hikari.Embed()
            embed.title = "Help"
            embed.description = ""
            for descr in page:
                embed.description += f"\n{descr}"

        return embeds






def load(bot: T_bot):
    bot.add_plugin(Help(bot))