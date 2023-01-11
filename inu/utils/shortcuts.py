from typing import *

import hikari


def make_message_link(
    guild_id: int,
    channel_id: int,
    message_id: int,
):
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"


def get_guild_or_channel_id(interaction: hikari.ComponentInteraction) -> int:
    if isinstance(interaction.user, hikari.Member):
        return interaction.user.guild_id
    return interaction.channel_id