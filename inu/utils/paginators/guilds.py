from typing import *  # noqa
from hikari import ComponentInteraction, Embed, Guild

from . import Paginator, listener
from utils import user_name_or_id
from core import InuContext



class GuildsPaginator(Paginator):
    _guilds: List[Guild]
    
    async def start(self, ctx: InuContext, guilds: List[Guild]):
        self._guilds = guilds
        self.set_embeds()
        await super().start(ctx)
        
    def set_embeds(self):
        embeds: List[Embed] = []
        for guild in self._guilds:
            embed = Embed(title=f"{guild.name}")
            
            embed.add_field("ID", f"{guild.id}", inline=True)
            embed.add_field("Owner", f"{user_name_or_id(guild.owner_id)}", inline=True)
            embed.add_field("Amount of Members", f"{len(guild.get_members())}", inline=True)
            embed.set_image(guild.icon_url)
            #embed.add_field("Roles", f"{len(guild.get_roles())}", inline=True)
            embeds.append(embed)
        self._pages = embeds
            

    # async def _update_position(self, interaction: ComponentInteraction | None = None,):
    #     """
    #     replaces embed page first with a more detailed one, before sending the message
    #     """
    #     await super()._update_position(interaction)
        
    # async def _load_details(self):
    #     """
    #     takes 
    #     """