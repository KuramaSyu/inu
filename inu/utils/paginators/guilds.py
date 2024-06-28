from typing import *  # noqa
from hikari import ButtonStyle, ComponentInteraction, Embed, GatewayGuild, Guild

from . import Paginator, listener, button  # use . to prevent circular imports 
from utils import user_name_or_id
from core import InuContext



class GuildPaginator(Paginator):
    _guilds: List[GatewayGuild]
    
    async def start(self, ctx: InuContext, guilds: List[GatewayGuild]):
        self._guilds = guilds
        self.set_embeds()
        await super().start(ctx)
        
    def set_embeds(self):
        embeds: List[Embed] = []
        for guild in self._guilds:
            embed = Embed(title=f"{guild.name}")
            
            embed.add_field("ID", f"{guild.id}", inline=False)
            embed.add_field("Owner", f"{user_name_or_id(guild.owner_id)}", inline=False)
            embed.add_field("Amount of Members", f"{len(guild.get_members())}", inline=False)
            embed.set_image(guild.icon_url)
            #embed.add_field("Roles", f"{len(guild.get_roles())}", inline=True)
            embeds.append(embed)
        self._pages = embeds
        
    @button(label="Leave Guild", custom_id_base="pag_guilds_leave", style=ButtonStyle.DANGER, emoji="🚪")
    async def leave_guild(self, ctx: InuContext, _):
        await ctx.respond("Test")

    # async def _update_position(self, interaction: ComponentInteraction | None = None,):
    #     """
    #     replaces embed page first with a more detailed one, before sending the message
    #     """
    #     await super()._update_position(interaction)
        
    # async def _load_details(self):
    #     """
    #     takes 
    #     """