import random
from typing import Optional, List

import hikari
from matplotlib.colors import cnames


embeds: List[hikari.Embed] = []
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
        """returns a random color from `cls.neon_colors`"""
        return hikari.Color.from_hex_code(
            cls.random_hex()
        )

    @staticmethod
    def from_name(color: str) -> hikari.Color:
        hex_ = cnames.get(str(color), None)
        if not isinstance(hex_, str):
            raise ColorNotFoundError(f"A color with name '{color}' wasn't found")
        return hikari.Color.from_hex_code(str(hex_))
    
    @classmethod
    def random_blue(cls) -> hikari.Color:
        return cls.from_name(random.choice(
                [
                "deepskyblue", "steelblue", "royalblue", "midnightblue", 
                "slateblue", "blueviolet", "darkviolet", "purple", 
                "darkblue", "navy", "mediumblue", "blue",
                "dodgerblue", "skyblue", "lightskyblue",
                "lightblue", "powderblue", "cadetblue", "darkturquoise",
                "slateblue", "darkslateblue", "mediumslateblue",
                ]
            )
        )
    @classmethod
    def pastel_color(self) -> hikari.Color:
        pass 

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





    