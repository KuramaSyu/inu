import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import *
from core import getLogger
# Set up logging
log = getLogger(__name__)

if TYPE_CHECKING:
    from .player import MusicPlayer

class VoiceState(ABC):
    """
    Abstract base class for Player voice states.
    Defines the interface for all concrete voice states.
    """
    def __init__(self, player: "MusicPlayer"):
        """Initialize with reference to the player"""
        self.player: "MusicPlayer" = player
    
    async def check_if_bot_is_alone(self) -> bool:
        """Check if the bot is alone, change state if needed"""
        bot = self.player.bot
        guild_id = self.player.guild_id

        if not guild_id:
            # theoretically this should never happen
            return False
        if not (voice_state := bot.cache.get_voice_state(guild_id, bot.me.id)):
            # not in a channel
            return False 
        if not (channel_id := voice_state.channel_id):
            # not in a channel
            return False
        other_states = [
            state 
            for state 
            in bot.cache.get_voice_states_view_for_channel(
                guild_id, channel_id
            ).values()
            if state.user_id != bot.me.id
        ]
        
        if len(other_states) == 0:
            return True
        return False
        
    @abstractmethod
    async def on_bot_lonely(self):
        """Handle the event when bot becomes lonely"""
        pass
        
    @abstractmethod
    async def on_human_join(self):
        """Handle the event when a human joins the voice channel"""
        pass
    
    @abstractmethod
    async def change_state(self, new_state_class):
        """Change to a new state"""
        pass
        
    @abstractmethod
    async def update_message(self):
        """Update queue message with state-specific information"""
        pass


class BotIsLonelyState(VoiceState):
    """
    State representing when the bot is alone in a voice channel.
    Includes a timer to automatically disconnect after 10 minutes.
    """
    WAIT_MINUTES = 10

    def __init__(self, player: "MusicPlayer"):
        super().__init__(player)
        self.disconnect_task = None
        self.disconnect_time = None
        # Start the disconnect timer
        self._start_disconnect_timer()
        
    def _start_disconnect_timer(self):
        """Start the disconnect timer task"""
        
        if self.disconnect_task:
            self.disconnect_task.cancel()
        
        self.disconnect_time = datetime.now() + timedelta(minutes=self.WAIT_MINUTES)
        self.disconnect_task = asyncio.create_task(self._disconnect_after_timeout())
        # the message for the leave in 10 minutes is created by on_bot_lonly by calling update_message
        
    async def _disconnect_after_timeout(self):
        """Disconnect the bot after 10 minutes of being alone"""
        try:
            await asyncio.sleep(self.WAIT_MINUTES*60)
            log.info(f"Bot was alone for {self.WAIT_MINUTES} minutes in guild {self.player.guild.name}, leaving voice channel")
            self.player.queue.add_footer_info(f"I left the channel because I was alone for {self.WAIT_MINUTES} minutes")
            await self.player.send_queue()
            await self.player.leave(silent=True)
        except asyncio.CancelledError:
            log.info(f"Disconnect timer cancelled in guild {self.player.guild.name}")
    
    async def update_message(self):
        """Update queue message with lonely state information"""
        await self.player.pause(paused_by=self.player.ctx.bot.me)
        self.player.queue.add_footer_info(f"I'll leave the channel in {self.WAIT_MINUTES} Minutes")
        await self.player.send_queue()
        
    async def on_bot_lonely(self):
        """Bot is already lonely, no action needed"""
        pass
        
    async def on_human_join(self):
        """When a human joins, change to active state"""
        await self.change_state(BotIsActiveState)
        
    async def change_state(self, new_state_class):
        """Change to a new state and cancel the disconnect timer"""
        if self.disconnect_task:
            self.disconnect_task.cancel()
            self.disconnect_task = None
        
        log.info(f"Changing state from BotIsLonelyState to {new_state_class.__name__} in guild {self.player.guild.name}")
        self.player.voice_state = new_state_class(self.player)


class BotIsActiveState(VoiceState):
    """
    State representing when the bot is in a voice channel with users.
    Normal playback operations occur in this state.
    """
    def __init__(self, player):
        super().__init__(player)
        asyncio.create_task(self._update_queue_message())
        
    async def _update_queue_message(self):
        """Update the queue message to remove the disconnect timer notice"""
        ...
        
    async def update_message(self):
        """Update queue message for active state"""
        # Remove any disconnect timer notices
        self.player.queue.reset_footer()
        await self.player.resume(self.player.bot.me)
        await self.player.send_queue()
        
    async def on_bot_lonely(self):
        """Handle the bot becoming lonely"""
        await self.change_state(BotIsLonelyState)
        
    async def on_human_join(self):
        """Already in active state with humans, no change needed"""
        pass
        
    async def change_state(self, new_state_class: Type[VoiceState]):
        """Change to a new state"""
        guild = self.player.bot.cache.get_guild(self.player.guild_id)
        assert guild
        log.info(f"Changing state from BotIsActiveState to {new_state_class.__name__} in guild {guild.name}")
        self.player.voice_state = new_state_class(self.player)
