from datetime import datetime
from typing import *  # noqa
from hikari import ButtonStyle, ComponentInteraction, Embed, GatewayGuild, Guild

from . import Paginator, listener, button  # use . to prevent circular imports 
from utils import user_name_or_id, CurrentGamesManager, TagManager, SettingsManager
from core import InuContext, getLogger

log = getLogger(__name__)


class GuildPaginator(Paginator):
    _guilds: List[GatewayGuild]
    
    async def start(self, ctx: InuContext, guilds: List[GatewayGuild]):
        self._guilds = guilds
        await self.set_embeds()
        await super().start(ctx)
        
    @property
    def guild(self) -> GatewayGuild:
        return self._guilds[self._position]
        
    async def set_embeds(self):
        embeds: List[Embed] = []
        for guild in self._guilds:
            embed = Embed(title=f"{guild.name}")
            
            embed.add_field("ID", f"{guild.id}", inline=True)
            embed.add_field("Owner", f"{user_name_or_id(guild.owner_id)}", inline=True)
            embed.add_field("Amount of Members", f"{len(guild.get_members())}", inline=True)
            
            # current games
            activities = await CurrentGamesManager.fetch_activities(self.guild.id, datetime(2021, 1, 1))
            enabled = await SettingsManager.fetch_activity_tracking(self.guild.id)
            embed.add_field("Current Games", f"Enabled: {enabled}\nDB Entries: {len(activities)}", inline=True)
            
            # tags
            # TODO
            embed.set_image(guild.icon_url)
            #embed.add_field("Roles", f"{len(guild.get_roles())}", inline=True)
            embeds.append(embed)
        self._pages = embeds
        
    @button(label="Leave Guild", custom_id_base="pag_guilds_leave", style=ButtonStyle.DANGER, emoji="🚪")
    async def leave_guild(self, ctx: InuContext, _):
        guild = self._guilds[self._position]
        log.warning(f"Leaving guild {guild.name}")
        await self.bot.rest.leave_guild(guild.id)
        try:
            await ctx.respond(f"Left guild {guild.name}")
        except Exception as e:
            pass
        
    @button(label="test", custom_id_base="test")
    async def test(self, ctx: InuContext, _):
        await ctx.respond("test")