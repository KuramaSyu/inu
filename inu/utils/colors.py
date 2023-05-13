import random
from typing import Optional, List, overload

import hikari
from matplotlib.colors import cnames
from colormap import rgb2hex, rgb2hls, hls2rgb

from core import ConfigProxy


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
    _conf: ConfigProxy = ConfigProxy()

    @classmethod
    def color_variant(cls, hex_color, brightness_factor) -> str:
        """ takes a color like #87c95f and produces a lighter or darker variant """
        if len(hex_color) != 7:
            raise Exception("Passed %s into color_variant(), needs to be in #87c95f format." % hex_color)
        rgb_hex = [hex_color[x:x+2] for x in [1, 3, 5]]
        new_rgb_int = [int(int(hex_value, 16) * brightness_factor) for hex_value in rgb_hex]
        #new_rgb_int = [min([255, max([0, i])]) for i in new_rgb_int] # make sure new values are between 0 and 255
        # hex() produces "0x88", we want just "88"
        return "#" + "".join([hex(i)[2:] for i in new_rgb_int])
    @classmethod
    def hex_to_rgb(cls, hex):
        hex = hex.lstrip('#')
        hlen = len(hex)
        return tuple(int(hex[i:i+hlen//3], 16) for i in range(0, hlen, hlen//3))

    @classmethod
    def adjust_color_lightness(cls, r, g, b, factor) -> str:
        # h, l, s = rgb2hls(r / 255.0, g / 255.0, b / 255.0)
        # l = max(min(l * factor, 1.0), 0.0)
        # r, g, b = hls2rgb(h, l, s)
        # return rgb2hex(int(r * 255), int(g * 255), int(b * 255))
        return rgb2hex(int(r * factor), int(g * factor), int(b * factor))

    @classmethod
    def darken_color(cls, r, g, b, factor=0.1) -> str:
        return cls.adjust_color_lightness(r, g, b, 1 - factor)

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

    @overload
    @classmethod
    def from_name(cls, color: str) -> hikari.Color:
        ...

    @overload
    @classmethod
    def from_name(cls, color: str, as_hex: bool) -> str:
        ...

    @classmethod
    def from_name(cls, color: str, as_hex: bool = False):
        if as_hex:
            hex_ = cnames.get(str(color), None)
            if not isinstance(hex_, str):
                raise ColorNotFoundError(f"A color with name '{color}' wasn't found")  
            return hex_  
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
    def pastel_color(cls) -> hikari.Color:
        """Returns a random pastel color."""
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        pastel_hex = cls.adjust_color_lightness(r, g, b, factor=0.8)
        return hikari.Color.from_hex_code(pastel_hex)
    
    @overload
    @classmethod
    def default_color(cls, darken_factor: float = 0, as_hex: bool = True) -> str:
        """
        Returns:
        --------
        str:
            format: #000000
        """
        ...

    @overload
    @classmethod
    def default_color(cls, darken_factor: float = 0, as_hex: bool = False) -> hikari.Color:
        ...


    @classmethod
    def default_color(cls, darken_factor: float = 0, as_hex: bool = False):
        """
        Args:
        -----
        darken_factor: float
            The factor by which the default color should be darkened. -255 to 255
        """
        try:
            hex_ = str(hex(int(cls._conf.bot.color, 16))).replace("0x", "#")
        except Exception:
            hex_ = cls.from_name(cls._conf.bot.color, as_hex=True)
        if darken_factor != 0:
            rgb = cls.hex_to_rgb(hex_)
            darken_hex = cls.darken_color(rgb[0], rgb[1], rgb[2], darken_factor)
            #darken_hex = cls.color_variant(hex_, brightness_factor=darken_factor)
        else:
            darken_hex = hex_
        if as_hex:
            return darken_hex
        return hikari.Color.from_hex_code(str(darken_hex))


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





    