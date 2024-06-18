from argparse import Action
from typing import *

import hikari
from hikari.impl import MessageActionRowBuilder

class AutoButton:
    def __init__(self) -> None:
        self._action_rows: List[MessageActionRowBuilder] = []

    @property
    def _last_builder(self) -> MessageActionRowBuilder:
        if not self._action_rows:
            self._action_rows.append(MessageActionRowBuilder())
        last_builder = self._action_rows[-1]
        if len(last_builder.components) >= 5:
            self._action_rows.append(MessageActionRowBuilder())
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

class MessageActionRowEditor():
    def __init__(self, action_row: MessageActionRowBuilder) -> None:
        self.action_row = action_row

    def disable_all(self) -> "MessageActionRowEditor":
        """
        Disable all buttons in the action row
        """
        for component in self.action_row._components:
            if isinstance(component, hikari.ButtonComponent):
                component.set_is_disabled(True)
        return self
    
    def set_styles(self, colors: List[hikari.ButtonStyle] | hikari.ButtonStyle) -> "MessageActionRowEditor":
        """
        Set colors for all buttons in the action row
        """
        if isinstance(colors, hikari.Color):
            colors = [colors] * len(self.action_row._components)
        for i, component in enumerate(self.action_row._components):
            if isinstance(component, hikari.ButtonComponent):
                component.style = colors[i]
        return self
    
    def mock_labels(self, labels: List[str] = None) -> "MessageActionRowEditor":
        """
        Set labels for all buttons in the action row
        """
        if labels is None:
            labels = [f"Mock_{i}" for i in range(len(self.action_row._components))]
        for i, component in enumerate(self.action_row._components):
            if isinstance(component, hikari.ButtonComponent):
                component.label = labels[i]
        return self
    
            

    

