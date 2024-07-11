from datetime import datetime, timedelta
from typing import *  # noqa
from hikari import ButtonStyle, ComponentInteraction, Embed, GatewayGuild, Guild
from humanize import naturaldelta

from . import Paginator, listener, button  # use . to prevent circular imports 
from utils import user_name_or_id, CurrentGamesManager, TagManager, SettingsManager, InvokationStats
from core import InuContext, getLogger

log = getLogger(__name__)


class GuildPaginator(Paginator):
    _guilds: List[GatewayGuild]
    
    async def start(self, ctx: InuContext, guilds: List[GatewayGuild]):
        self._guilds = guilds
        self.set_context(ctx)
        await self.ctx.respond("collecting data...")
        self._pages = ["Wait" for _ in guilds]
        await self._update_position()
        await super().start(ctx)
        
    @property
    def guild(self) -> GatewayGuild:
        return self._guilds[self._position]
        
    async def make_embed(self, page: int) -> Embed:
        guild = self._guilds[page]
        
        embed = Embed(title=f"{guild.name}")
        embed.add_field("ID", f"{guild.id}", inline=False)
        embed.add_field("Owner", f"{user_name_or_id(guild.owner_id)}", inline=False)
                    
        # current games
        activities = await CurrentGamesManager.fetch_activities(guild.id, datetime(2021, 1, 1))
        activity_duration = naturaldelta(timedelta(hours=len(activities) * (1/6)))
        enabled = await SettingsManager.fetch_activity_tracking(guild.id)
        embed.add_field("Current Games", f"**Enabled:** {enabled}\n**Entries:** {len(activities)} ({activity_duration})", inline=False)
        
        # Members
        embed.add_field("Amount of Members", f"{len(guild.get_members())}", inline=True)

        # tags
        tag_amount = await TagManager.fetch_guild_tag_amount(guild.id)
        embed.add_field("Tags", f"Amount: {tag_amount}", inline=True)
        
        # amount of commands used
        invocations = await InvokationStats.fetch_json(guild.id)
        if invocations:
            invovation_amount = sum(invocations.values())
        else:
            invovation_amount = 0
        embed.add_field("Command Usage", f"{invovation_amount} Commands used")
        embed.set_image(guild.icon_url)
        
        return embed 
    
    
    async def set_embeds(self):
        embeds: List[Embed] = []
        for _ in self._guilds:
            embed = await self.make_embed(self._position)
            embeds.append(embed)
        self._pages = embeds
        
    
    async def _update_position(self, interaction: ComponentInteraction | None = None):
        self._pages[self._position] = await self.make_embed(self._position)
        return await super()._update_position(interaction)
        
    @button(label="Leave Guild", custom_id_base="pag_guilds_leave", style=ButtonStyle.DANGER, emoji="🚪")
    async def leave_guild(self, ctx: InuContext, _):
        try:
            ans, ctx = await ctx.ask(
                f"Are you sure to leave `{self.guild.name}`?", 
                ["Yes", "No"],
                allowed_users=[ctx.author.id]
            )
        except Exception as e:
            return
        if ans != "Yes":
            return
        guild = self._guilds[self._position]
        log.warning(f"Leaving guild {guild.name}")
        await self.bot.rest.leave_guild(guild.id)
        try:
            await ctx.respond(f"Left guild {guild.name}")
        except Exception as _:
            pass
        
    @button(label="Toggle Activity Tracking", custom_id_base="pag_guilds_toggle", style=ButtonStyle.PRIMARY, emoji="🎮")
    async def toggle_activity_tracking(self, ctx: InuContext, _):
        guild = self._guilds[self._position]
        self.set_context(ctx)
        await self.ctx.defer(update=True)
        enabled = await SettingsManager.fetch_activity_tracking(guild.id)
        await SettingsManager.update_activity_tracking(guild.id, enable=not enabled)
        await self.set_embeds()
        await self._update_position()
    