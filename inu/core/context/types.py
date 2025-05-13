from typing import *
import hikari

T_STR_LIST = TypeVar("T_STR_LIST", list[str], str)
TInteraction = TypeVar("TInteraction", hikari.ModalInteraction, hikari.CommandInteraction)