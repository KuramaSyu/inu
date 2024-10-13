from typing import *
from hikari import ButtonStyle
from hikari.impl import MessageActionRowBuilder


class MusicMessageComponents:
    def __init__(self):
        self._disable_all = False
        self._is_paused = False
    
    def disable(self, disable: bool = True) -> "MusicMessageComponents":
        self._disable_all = disable
        return self
    
    def pause(self, pause: bool = False) -> "MusicMessageComponents":
        self._is_paused = pause
        return self
    
    def build(
        self,
    ) -> List[MessageActionRowBuilder]:
        """builds the components for the music message
        
        Args:
        ----
        disable_all : bool=False
            If all buttons should be disabled, by default False
        """
        is_paused = self._is_paused
        paused_or_stopped = self._is_paused
        disable_all = self._disable_all

        action_rows = [
            (
                MessageActionRowBuilder()
                .add_interactive_button(
                    ButtonStyle.SECONDARY, 
                    "music_skip_1",
                    is_disabled=disable_all or is_paused,
                    emoji="1️⃣",
                )
                .add_interactive_button(
                    ButtonStyle.SECONDARY,
                    "music_skip_2",
                    emoji="2️⃣",
                    is_disabled=disable_all or is_paused,
                )
                .add_interactive_button(
                    ButtonStyle.SECONDARY,
                    "music_shuffle",
                    emoji="🔀",
                    is_disabled=disable_all,
                )
                .add_interactive_button(
                    ButtonStyle.SECONDARY,
                    "music_stop",
                    emoji="🛑",
                    is_disabled=disable_all,
                )
            )
        ]
        if not disable_all:
            if is_paused:
                action_rows[0].add_interactive_button(
                    ButtonStyle.PRIMARY,
                    "music_resume",
                    emoji="▶",
                )
            else:
                action_rows[0].add_interactive_button(
                    ButtonStyle.SECONDARY,
                    "music_pause",
                    emoji="⏸",
                )
        return action_rows