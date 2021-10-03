from types import TracebackType
import discord
from typing import Union, Optional, List
import traceback

from .Paginator import BaseAdvancedPaginator

class MusicHistoryPaginator(BaseAdvancedPaginator):
    def __init__(
        self,
        *,
        links_sorted: list[dict],
        pages: Optional[Union[List[discord.Embed], discord.Embed]] = None,
        compact: bool = False,
        timeout: float = 60.0,
        has_input: bool = True,
        reactions_to_add: list[str] = [],
        remove_reactions: bool = False,
        enable_message: bool = True,
        enable_reaction_add: bool = True,
        enable_reaction_remove: bool = True,
        enable_message_edit: bool = False,
        enable_message_remove: bool = False,
    ):
        super().__init__(
            # self,
            pages=pages,
            compact=compact,
            timeout=timeout,
            has_input=has_input,
            reactions_to_add=reactions_to_add,
            remove_reactions=remove_reactions,
            enable_message=enable_message,
            enable_reaction_add=enable_reaction_add,
            enable_reaction_remove=enable_reaction_remove,
            enable_message_edit=enable_message_edit,
            enable_message_remove=enable_message_remove,
        )
        self.not_valid = 0
        self.song_list = links_sorted
    
    async def on_start(self):
        print("on_start")
        try:
            cog = self.client.get_cog("InuLavalink")
            self.play = cog.play
            self.not_valid = 0
        except:
            traceback.print_exc()
        

    async def on_message(self, message):
        if self.not_valid > 2:
            self.timeout = 10
        print(message.content)
        valid = [str(num) for num in range(10)]
        valid.extend([" ", ","])
        for char in set(message.content):
            if char not in valid:
                self.not_valid += 1
                print("unvalid char ", char)
                return
        numbers = []
        number = ""
        for char in message.content:
            if char.isdigit():
                number += char
            elif char in [" ", ","] and number:
                numbers.append(int(number))
                number = ""
            print(numbers, "X", number)
        else:
            if number:
                numbers.append(int(number))

            
        if numbers == []:
            return

        links = []
        embed = discord.Embed()
        embed.title = "Add Songs:"
        embed.description = ""
        embed.color = discord.Color.blurple()
        embed.set_thumbnail(url=self.ctx.author.avatar_url)
        embed.set_footer(
            text=f"{len(numbers)} {'track is' if len(numbers) <= 1 else 'tracks are'} "\
                 f"added by {self.ctx.author.display_name}"
        )
        for num in numbers:
            d = self.song_list[num]
            embed.description += f"{num} | [{d['title']}]({d['url']})\n"
            links.append(d["url"])
        await self.ctx.send(embed=embed)
        await self.play(self.ctx, query=links)


        

    