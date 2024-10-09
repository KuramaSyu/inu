from typing import *
from datetime import datetime, timedelta
import hikari
from hikari.impl import MessageActionRowBuilder
import aiohttp

from core import Inu, getLogger
from utils import pacman

log = getLogger(__name__)
# Pictures
MAGIC_ERROR_MONSTER = "https://media.discordapp.net/attachments/818871393369718824/1106177322069012542/error-monster-1.png?width=1308&height=946"

bot: Inu = None

def set_bot(bot_: Inu):
    global bot
    bot = bot_
    log.debug(f"Bot set in shortcuts: {bot = }")


def make_message_link(
    guild_id: int,
    channel_id: int,
    message_id: int,
):
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"


def get_guild_or_channel_id(interaction: hikari.ComponentInteraction) -> int:
    """
    Returns the guild_id if not None, otherwise the (DM) channel_id 
    """
    return interaction.guild_id or interaction.channel_id

def guild_name_or_id(guild_id: int, *args, **kwargs) -> str:
    """
    returns the name of the guild_id if in cache, otherwise the ID as string

    Args:
    -----
    guild_id : int
        the id of the guild
    bot : hikari.CacheAware
        A cache aware bot, to check if guild is in cache
    """
    guild = bot.cache.get_guild(guild_id)
    return guild.name if guild else str(guild_id)

def user_name_or_id(user_id: int, *args, **kwargs) -> str:
    """
    returns the name of the user_id if in cache, otherwise the ID as string

    Args:
    -----
    user_id : int
        the id of the user
    bot : hikari.CacheAware
        A cache aware bot, to check if user is in cache
    """
    user = bot.cache.get_user(user_id)
    return user.global_name or user.username if user else str(user_id)

def display_name_or_id(user: hikari.SnowflakeishOr[hikari.Member], guild_id: int | None = None, *args, **kwargs) -> str:
    """
    returns the name of the user_id if in cache, otherwise the ID as string

    Args:
    -----
    user_id : int
        the id of the user
    guild_id : int | None
        the id of the guild if user is not a member

    """
    if guild_id or isinstance(user, hikari.Member):
        member = bot.cache.get_member(guild_id or user.guild_id, user)
        return member.display_name if member else str(user)
    else:
        member = bot.cache.get_user(user)
        return member.username if member else str(member)

def ts_round(delta: timedelta, round_to: timedelta) -> timedelta:
    total_seconds = delta.total_seconds()
    rounded_seconds = round(total_seconds / round_to.total_seconds()) * round_to.total_seconds()
    return timedelta(seconds=rounded_seconds)



async def check_website(url: str) -> Tuple[int, Optional[str]]:
    """
    Checks if a website is available

    Returns:
    --------
    Tuple[int, Optional[str]]
        the status code and an optional error message
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return response.status, response.reason
    except aiohttp.ClientError as e:
        return 0, str(e)
    
def has_component_interaction(event: hikari.InteractionCreateEvent) -> bool:
    """
    Whether or not the event has a ComponentInteraction
    """
    if isinstance(event.interaction, hikari.ComponentInteraction):
        return True
    return False

def mockup_action_row(
        button_labels: List[str],
        is_disabled: List[bool] | bool,
        colors: List[hikari.ButtonStyle] | hikari.ButtonStyle,
) -> MessageActionRowBuilder:
    if isinstance(is_disabled, bool):
        is_disabled = [is_disabled] * len(button_labels)
    if isinstance(colors, hikari.ButtonStyle):
        colors = [colors] * len(button_labels)
    action_row = MessageActionRowBuilder()
    for label, disabled, color in zip(button_labels, is_disabled, colors):
        action_row.add_interactive_button(
            color, 
            f"mockup_{label}",
            label=label, 
            is_disabled=disabled
        )
    return action_row


class ButtonUtils:
    @classmethod
    def toggle_by_label(
        cls,
        row: List[MessageActionRowBuilder] | MessageActionRowBuilder,
        label: str,
        disable: bool = True,
    ) -> List[MessageActionRowBuilder]:
        """
        Toggles the disabled state of a button in a message action row based on its label.

        Args:
            row (List[MessageActionRowBuilder] | MessageActionRowBuilder): The row or rows of buttons.
            label (str): The label of the button to toggle.
            disable (bool, optional): Whether to disable the button. Defaults to True.
        
        Returns:
            List[MessageActionRowBuilder]: The updated row.
        """
        if isinstance(row, MessageActionRowBuilder):
            row = [row]
        
        for action_row in row:
            for button in action_row.components:
                if button.type == hikari.ComponentType.BUTTON and button.label == label:
                    button.is_disabled = disable
        return row



    