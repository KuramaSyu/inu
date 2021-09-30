import logging
import typing
from typing import Tuple, Union, Optional, List
import os

import hikari
import lightbulb

from core import Inu
from utils import Color
from utils.language import Multiple

log = logging.getLogger(__name__)



class CodeSize(lightbulb.Plugin):
    def __init__(self, bot: Inu):
        self.bot = bot
        self.dirs = ['extensions',  'models', 'utils']
        super().__init__(name="CodeSize")

    def get_directory_size(self, directory: str) -> Tuple[int, int]:
        """Returns the `directory` size in bytes. and the count of all lines"""
        total = 0
        lines = 0
        try:
            for entry in os.scandir(directory):
                if (
                    entry.is_file()
                    and not (
                        Multiple.endswith_(
                            entry.name, 
                            [".png", ".jpg", ".gif", ".exe",
                             ".bin", ".log", ".mp4", ".mp3"]
                        )
                    )
                ):
                    total += entry.stat().st_size
                    lines += sum(1 for _ in open(entry.path, "r+", encoding="utf-8"))
                elif entry.is_dir() and not entry.name == "__pycache__":
                    size, lines = self.get_directory_size(entry.path)
                    total += size
                    lines += lines
        except NotADirectoryError as nd:
            log.debug(nd)
            return (os.path.getsize(directory), 0)
        except PermissionError:
            # if for whatever reason we can't open the folder, return 0
            return 0, 0
        return total, lines


    @lightbulb.command()
    async def code(self, ctx: lightbulb.Context):
        '''
        How many bytes/code lines am I?
        '''
        size_in_bytes, lines = self.get_directory_size(f'{os.getcwd()}/inu')
        text = (
            f"I am written out of\n**{int(size_in_bytes)*8} bits**"
            f" (**{round(float(size_in_bytes / 1000))}Kb | "
            f"{round(float(size_in_bytes / 1000 / 1000),1)}mb**)\n"
            f"1 typical letter is 1 byte/ 8 bit big\nMeans that'"
            f"I am written out of\n**{size_in_bytes} letters**\n"
            f"or\n**{lines} lines**\nof code"
        )
        embed = hikari.Embed(
            title="Code",
            description=text,
        )
        embed.set_thumbnail(str(self.bot.me.avatar_url))
        embed.color = Color.from_name("slateblue")
        await ctx.respond(embed=embed)

def load(bot: Inu):
    bot.add_plugin(CodeSize(bot))
