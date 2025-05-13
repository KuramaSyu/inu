import os
from typing import Tuple

import hikari
from hikari import ApplicationContextType

import lightbulb
from lightbulb import SlashCommand, invoke

from core import Inu, InuContext, getLogger
from utils import Colors, Human
from utils.language import Multiple

log = getLogger(__name__)

loader = lightbulb.Loader()
bot = Inu.instance

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
                            ".bin", ".log", ".mp4", ".mp3", "Lavalink.jar", ".pyc", ".pyo",
                            "LICENCE", "md", 
                        ]
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
        log.debug(f"{nd}")
        return (os.path.getsize(directory), 0)
    except PermissionError:
        # if for whatever reason we can't open the folder, return 0
        return 0, 0
    return total, lines

@loader.command
class CodeCommand(
    SlashCommand,
    name="code",
    description="Shows information about the amount of code I have",
    contexts=[ApplicationContextType.GUILD],
    default_member_permissions=None,
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        size_in_bytes, lines = get_directory_size(f'{os.getcwd()}/inu')
        book_count = round(float(size_in_bytes/(60 * 30 * 250)), 2)
        text = (
            f"I am written out of\n**{Human.number(int(size_in_bytes)*8)} Bits**"
            f" (**{Human.number(round(float(size_in_bytes / 1000)))}kB | "
            f"{Human.number(round(float(size_in_bytes / 1000 / 1000),1))}MB**)\n"
            f"One typical letter has a size of 1 Byte (8 Bit)\nMeans that "
            f"I am written out of\n- **{Human.number(size_in_bytes)} letters**\n"
            f"- or **{Human.number(lines)} lines** of code\n"
            f"- or **{book_count} {Human.plural_('book', book_count, with_number=False)}**"
            f" with 250 pages (and 30 lines which each have 60 characters)"
        )
        # 60 chars per line, 30 lines per page, 250 pages per book
        embed = hikari.Embed(
            title="Code",
            description=text,
        )
        embed.set_thumbnail(str(ctx.bot.me.avatar_url))
        embed.color = Colors.from_name("slateblue")
        await ctx.respond(embed=embed)