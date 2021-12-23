import logging
import typing
from typing import Tuple, Union, Optional, List
import os

import hikari
import lightbulb
from lightbulb.context import Context
from lightbulb import commands

from core import Inu
from utils import Colors, Human
from utils.language import Multiple
num = Human.number

log = logging.getLogger(__name__)



plugin = lightbulb.Plugin("Code", "Information to the ammount of code")

def get_directory_size(directory: str) -> Tuple[int, int]:
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
                            ".bin", ".log", ".mp4", ".mp3", "Lavalink.jar"]
                    )
                )
            ):
                total += entry.stat().st_size
                try:
                    lines += sum(1 for _ in open(entry.path, "r+", encoding="utf-8"))
                except:
                    pass
            elif entry.is_dir() and not entry.name == "__pycache__":
                size, n_lines = get_directory_size(entry.path)
                total += size
                lines += n_lines
    except NotADirectoryError as nd:
        log.debug(nd)
        return (os.path.getsize(directory), 0)
    except PermissionError:
        # if for whatever reason we can't open the folder, return 0
        return 0, 0
    return total, lines

@plugin.command
@lightbulb.command("code", "Shows information to the ammount of code I have")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def code(ctx: Context):
    '''
    How many bytes/code lines am I?
    '''
    size_in_bytes, lines = get_directory_size(f'{os.getcwd()}/inu')
    text = (
        f"I am written out of\n**{num(int(size_in_bytes)*8)} bits**"
        f" (**{num(round(float(size_in_bytes / 1000)))}Kb | "
        f"{num(round(float(size_in_bytes / 1000 / 1000),1))}mb**)\n"
        f"1 typical letter is 1 byte/ 8 bit big\nMeans that'"
        f"I am written out of\n**{num(size_in_bytes)} letters**\n"
        f"or\n**{num(lines)} lines**\nof code"
    )
    embed = hikari.Embed(
        title="Code",
        description=text,
    )
    embed.set_thumbnail(str(plugin.bot.me.avatar_url))
    embed.color = Colors.from_name("slateblue")
    await ctx.respond(embed=embed)

def load(bot: Inu):
    bot.add_plugin(plugin)
