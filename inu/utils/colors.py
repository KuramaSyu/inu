import random
from typing import Optional

import hikari
from matplotlib.colors import cnames


embeds = []
colors = [  "orange", "darkorange", "firebrick", "yellowgreen", "limegreen", "mediumturquoise",
            "teal", "deepskyblue", "steelblue", "royalblue", "midnightblue",
            "slateblue", "blueviolet", "darkviolet", "purple", "crimson"
]
def random_color() -> str:
    
    return cnames[random.choice(colors)]

class Colors():

    neon_colors = [
        "orange", "darkorange", "firebrick", "yellowgreen", "limegreen", "mediumturquoise",
        "teal", "deepskyblue", "steelblue", "royalblue", "midnightblue",
        "slateblue", "blueviolet", "darkviolet", "purple", "crimson"
    ]

    @classmethod
    def random_hex(cls) -> str:
        """returns a hexlike string (#000000)"""
        return cnames[random.choice(cls.neon_colors)]

    @classmethod
    def random_color(cls) -> hikari.Color:
        return hikari.Color.from_hex_code(
            cls.random_hex()
        )

class ColorNotFoundError(Exception):
    def __init__(self, message: Optional[str]):
        super().__init__(message)
        

class Color():
    @staticmethod
    def from_name(color: str) -> hikari.Color:
        hex_ = cnames.get(str(color), None)
        if not isinstance(hex_, str):
            raise ColorNotFoundError(f"A color with name '{color}' wasn't found")
        return hikari.Color.from_hex_code(str(hex_))





    