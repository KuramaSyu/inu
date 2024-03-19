from typing import *
from datetime import datetime, timedelta
import hikari
from hikari.impl import MessageActionRowBuilder
from abc import ABC, abstractclassmethod

from core import InuContext
from utils import pacman

class Button(ABC):
    @abstractclassmethod
    def add(
        cls,
        row: List[MessageActionRowBuilder],
        *args: Any,
        **kwargs: Any
    ) -> List[MessageActionRowBuilder]:
        pass


def add_row_when_filled(
        row: List[MessageActionRowBuilder], 
        position: int = -1, 
        min_empty_slots: int = 1
) -> List[MessageActionRowBuilder]:
    """
    Adds a MessageActionRowBuilder to the List if the last one has no free component-slots

    Args:
    -----
    row : List[MessageActionRowBuilder]
        the row inspect
    position : int
        where to insert the new row if possible
    """
    min_empty_slots -= 1
    if not row:
        return [MessageActionRowBuilder()]
    if len(row[-1].components) >= 5 - min_empty_slots:
        if len(row) >= 5:
            raise RuntimeWarning("Can't add more than 5 rows")
        if position == -1:
            row.append(MessageActionRowBuilder())
        else:
            row.insert(position, MessageActionRowBuilder())
    return row

class TimeButton(Button):
    @classmethod
    def add(
        cls,
        row: List[MessageActionRowBuilder], 
        time: datetime = None
    ) -> List[MessageActionRowBuilder]:
        """
        Adds a time button to the last actionrowbuilder or to a new one if the last one is full.

        Args:
            row (List[MessageActionRowBuilder]): The list of action row builders.
            time (datetime, optional): The time to display on the button. Defaults to the current time.

        Returns:
            List[MessageActionRowBuilder]: The updated list of action row builders.
        """
        if not time:
            time = datetime.now()
        row = add_row_when_filled(row)
        row[-1].add_interactive_button(
                hikari.ButtonStyle.SECONDARY,
                f"ts_{time.hour}_{time.minute}",
                label=f"⏱️ {time.hour:02d}:{time.minute:02d}:{time.second:02d} UTC",
                is_disabled=True,
            )
        return row


class PacmanButton(Button):
    @classmethod
    def add(
        cls,
        row: List[MessageActionRowBuilder], 
        index: int, 
        length: int = 15, 
        short: bool = True, 
        increment: int = 1,
        color: hikari.ButtonStyle = hikari.ButtonStyle.SECONDARY,
    ) -> List[MessageActionRowBuilder]:
        """
        Adds a pacman progressbar button to the last action row builder or to a new one if the last one is full.

        Args:
            row (List[hikari.MessageActionRowBuilder]): The list of action row builders.
            index (int): The index of the pacman progressbar.
            length (int, optional): The length of the pacman progressbar. Defaults to 15.
            short (bool, optional): Whether to use a short version of the progressbar. Defaults to True.
            increment (int, optional): The increment value for the progressbar. Defaults to 1.
            color (hikari.ButtonStyle, optional): The color style of the button. Defaults to hikari.ButtonStyle.SECONDARY.

        Returns:
            List[hikari.MessageActionRowBuilder]: The updated list of action row builders.
        """
        pac = pacman(index, length, short=short, increment=increment)
        row = add_row_when_filled(row)
        row[-1].add_interactive_button(
            color,
            f"pacman",
            label=f"{pac.__next__()}",
            is_disabled=True,
        )
        return row


class ResendButton(Button):
    @classmethod
    def add(
        cls,
        row: List[MessageActionRowBuilder], 
        custom_id: str,
        color: hikari.ButtonStyle = hikari.ButtonStyle.SECONDARY,
    ) -> List[MessageActionRowBuilder]:
        """
        Adds a pacman progressbar button to the last actionrowbuilder or to a new one if last one is full

        Args:
        -----
        row : List[MessageActionRowBuilder]
            the row to add the button to
        custom_id : str
            the custom id of the button;
            should be like `resend-{fn_name}`
        """
        row = add_row_when_filled(row)
        row[-1].add_interactive_button(
            color,
            custom_id,
            label=f"send down",
            emoji="⤵️",
        )
        return row
