from argparse import Action
from typing import *

import hikari
from hikari.impl import ActionRowBuilder

class AutoButton:
    def __init__(self) -> None:
        self._action_rows: List[ActionRowBuilder] = []

    @property
    def _last_builder(self) -> ActionRowBuilder:
        if not self._action_rows:
            self._action_rows.append(ActionRowBuilder())
        last_builder = self._action_rows[-1]
        if len(last_builder.components) >= 5:
            self._action_rows.append(ActionRowBuilder())
        return last_builder

    def add_buttons(
        self,
        labels: List[str] | None = None,
        urls: List[str, None] | None = None,
        custom_ids: List[str, None] | None = None,
        styles : List[str | None] | None = None,
    ) -> "AutoButton":
        """
        create buttons. The index of all lists is the order
        Args:
        -----
        labels: List[str] | None
            - text of the button
            - if None: `<urls>` is needed
        urls: List[str | None] | None
            urls for the buttons as alternative to `<labels>`
        custom_ids: List[str | None] | None
        """
        ...
    async def ask(
        self,
        title: str | None,
        description: str | None,        
    ) -> Tuple[hikari.InteractionCreateEvent, hikari.ComponentInteraction, str] | None:
        """
        Returns:
        --------
        Tuple[hikari.InteractionCreateEvent, hikari.ComponentInteraction, str] | None:
            Tuple:
                - the event created by the buttom interaction
                - the interaction from the event
                - the custom_id from the button
            None:
                - no response
        None:
            no response was made
        """
        ...

    def set_callback(
        self,
        callback: Coroutine,
        button_custom_id: str | None,
        
    ) -> "AutoButton":
        """
        set callback for `<button_custom_id>` or the last created button
        """
        ...
    def execute_callback(self) -> Any:
        """
        Execute the proper callback according to the response of `self.ask`.

        Returns:
        --------
        Any:
            Whatever the callback returns
        """

