from typing import *
from abc import ABC, abstractmethod

from hikari import ButtonStyle
from hikari.impl import MessageActionRowBuilder, InteractiveButtonBuilder

if TYPE_CHECKING:
    from .base import Paginator


class ButtonBuilder:
    """
    A builder class for creating message action row buttons with customizable properties.
    This class provides a fluent interface for constructing buttons that can be added to
    a Discord message action row. It supports customization of position, label, style,
    custom ID, emoji, and disable conditions.

    Parameters
    ----------
    action_row_builder : MessageActionRowBuilder, optional
        The builder for the message action row, by default None

    Attributes
    ----------
    action_row_builder : MessageActionRowBuilder
        The builder for the message action row
    position : int
        The position of the button in the action row
    disable_when_index_is : Callable[[Optional[int]], bool]
        A function that determines when the button should be disabled
    label : str
        The text label of the button
    style : ButtonStyle
        The visual style of the button
    custom_id : str
        The custom identifier for the button
    emoji : str
        The emoji to display on the button

    Methods
    -------
    set_position(position: int)
        Sets the position of the button in the action row
    set_disable_condition(condition: Callable[[Optional[int]], bool])
        Sets the condition for when the button should be disabled
    set_label(label: str)
        Sets the text label of the button
    set_style(style: ButtonStyle)
        Sets the visual style of the button
    set_custom_id(custom_id: str)
        Sets the custom identifier for the button
    set_emoji(emoji: str)
        Sets the emoji to display on the button
    build()
        Constructs and returns the message action row with the configured button

    Examples
    --------
    >>> button = ButtonBuilder()\\
    ...     .set_position(0)\\
    ...     .set_label("Click Me")\\
    ...     .set_style(ButtonStyle.PRIMARY)\\
    ...     .set_custom_id("my_button")\\
    ...     .set_emoji("👍")\\
    ...     .build()
    """
    def __init__(self, action_row_builder: Optional[MessageActionRowBuilder] = None):
        self.action_row_builder = action_row_builder or MessageActionRowBuilder()
        self.position = 0
        self.disable_when_index_is = lambda x: False
        self.label = ""
        self.style = ButtonStyle.SECONDARY
        self.custom_id = None
        self.emoji = None

    def set_position(self, position: int) -> 'ButtonBuilder':
        self.position = position
        return self

    def set_disable_condition(self, condition: Callable[[Optional[int]], bool]) -> 'ButtonBuilder':
        self.disable_when_index_is = condition
        return self

    def set_label(self, label: str) -> 'ButtonBuilder':
        self.label = label
        return self

    def set_style(self, style: ButtonStyle) -> 'ButtonBuilder':
        self.style = style
        return self

    def set_custom_id(self, custom_id: str) -> 'ButtonBuilder':
        self.custom_id = custom_id
        return self

    def set_emoji(self, emoji: str) -> 'ButtonBuilder':
        self.emoji = emoji
        return self

    def build(self) -> MessageActionRowBuilder:
        state = self.disable_when_index_is(self.position)
        custom_id = self.custom_id or self.label
        btn = InteractiveButtonBuilder(style=self.style, custom_id=custom_id)
        btn.set_is_disabled(state)
        
        if self.emoji:
            btn.set_emoji(self.emoji)
        if self.label:
            btn.set_label(self.label)
            
        self.action_row_builder.add_component(btn)
        return self.action_row_builder


class NavigationStragegy(ABC):
    @abstractmethod
    def __init__(self, paginator: "Paginator") -> None:
        ...

    @abstractmethod
    def build(self) -> List[MessageActionRowBuilder]:
        ...

    @abstractmethod
    def set_rows_amount(self, amount: int) -> None:
        ...


class NumericNavigation(NavigationStragegy):
    def __init__(self, paginator: "Paginator") -> None:
        self.paginator = paginator
        self.rows: int = 4
    
    def set_rows_amount(self, amount: int) -> None:
        self.rows = amount

    def build(self) -> List[MessageActionRowBuilder]:
        pag = self.paginator
        page_len = len(pag._pages)
        position = pag._position
        row_amount = self.rows
        # calculate start and stop indices for the three cases
        BUTTONS_PER_ROW = 5
        BUTTON_AMOUNT = row_amount * BUTTONS_PER_ROW
        if position < BUTTONS_PER_ROW * 2:
            start = 0
            stop = min(BUTTON_AMOUNT, page_len)
        else:
            row_index = position // BUTTONS_PER_ROW
            if row_index < 2:
                start = 0
                stop = BUTTON_AMOUNT
            elif row_index > page_len // BUTTONS_PER_ROW - 2:
                stop = page_len
                start = max(
                    ((stop - BUTTON_AMOUNT) // BUTTONS_PER_ROW + 1) * BUTTONS_PER_ROW, 
                    0
                )
            else:
                start = (row_index - 2) * BUTTONS_PER_ROW
                stop = start + BUTTON_AMOUNT

        action_rows = []
        for i in range(start, stop, BUTTONS_PER_ROW):
            action_row = MessageActionRowBuilder()
            for j in range(i, min(i+BUTTONS_PER_ROW, stop)):
                button_index = j - start
                action_row = (ButtonBuilder(action_row)
                    .set_position(position)
                    .set_custom_id("stop" if j == position else f"pagination_page_{j}")
                    .set_label(str(j+1))
                    .set_disable_condition(lambda p: p == j)
                    .set_style(ButtonStyle.PRIMARY if j == position else ButtonStyle.SECONDARY)
                ).build()
            action_rows.append(action_row)

        return action_rows


class ClassicNavigation(NavigationStragegy):
    """
    A classic navigation strategy implementation using Discord UI buttons.
    This class implements a navigation strategy that creates a row of buttons for paginator control.
    The buttons include navigation controls (first, previous, next, last), a stop button, and
    optionally a sync button.
    The navigation controls are arranged as follows (in non-compact mode):
    ⏮ ◀ ✖ ▶ ⏭
    In compact mode, first (⏮) and last (⏭) buttons are omitted.

    Parameters
    ----------
    paginator : Paginator
        The paginator instance this navigation strategy is attached to.

    Methods
    -------
    build()
        Constructs and returns the message action rows containing navigation buttons.

    Returns
    -------
    List[MessageActionRowBuilder]
        A list of action rows containing the navigation buttons.
    """
    def __init__(self, paginator: "Paginator") -> None:
        self.paginator = paginator

    def set_rows_amount(self, amount: int) -> None:
        """does nothing"""
        return

    def build(self) -> List[MessageActionRowBuilder]:
        pag = self.paginator
        page_len = len(pag.pages)

        rows: List[MessageActionRowBuilder] = []
        action_row = None
        if not pag.compact:
            action_row = ButtonBuilder(action_row)\
                .set_custom_id("first")\
                .set_emoji("⏮")\
                .set_disable_condition(lambda p: p == 0)\
                .build()

        if page_len > 1:
            action_row = ButtonBuilder(action_row or MessageActionRowBuilder())\
                .set_custom_id("previous")\
                .set_emoji("◀")\
                .set_disable_condition(lambda p: p == 0)\
                .build()

        action_row = ButtonBuilder(action_row)\
            .set_custom_id("stop")\
            .set_emoji("✖")\
            .set_label(f"{pag._position+1}/{page_len}")\
            .set_style(ButtonStyle.DANGER)\
            .build()

        if page_len > 1:
            action_row = ButtonBuilder(action_row)\
                .set_custom_id("next")\
                .set_emoji("▶")\
                .set_disable_condition(lambda p: p == page_len-1)\
                .build()

        if not pag.compact:
            action_row = ButtonBuilder(action_row)\
                .set_custom_id("last")\
                .set_emoji("⏭")\
                .set_disable_condition(lambda p: p == page_len-1)\
                .build()

        rows.append(action_row)
        
        if pag._with_update_button:
            if len(action_row._components) >= 5:
                rows.append(MessageActionRowBuilder())
            rows[-1] = ButtonBuilder(rows[-1])\
                .set_custom_id("sync")\
                .set_emoji("🔁")\
                .build()

        return rows


def get_navigation_strategy(
    strategy_name: Literal["numeric", "classic"], 
    paginator: "Paginator"
) -> NavigationStragegy:
    """
    Factory function that returns a navigation strategy based on the provided name.

    Parameters
    ----------
    strategy_name : str
        The name of the strategy ('numeric' or 'classic')
    paginator : Paginator
        The paginator instance to attach to the strategy

    Returns
    -------
    NavigationStragegy
        The requested navigation strategy instance
    """
    strategies = {
        'numeric': NumericNavigation,
        'classic': ClassicNavigation
    }
    
    strategy_class = strategies.get(strategy_name.lower())
    if not strategy_class:
        raise ValueError(f"Unknown navigation strategy: {strategy_name}")
    
    return strategy_class(paginator)