from typing import *

class Emoji:
    numbers = {num: as_str for num, as_str in enumerate([r"0️⃣",r"1️⃣",r"2️⃣",r"3️⃣",r"4️⃣",r"5️⃣",r"6️⃣",r"7️⃣",r"8️⃣",r"9️⃣",r"🔟"])}
    _color_names = ["red", "orange", "yellow", "green", "blue", "purple", "brown", "black", "white"]
    colors_round = {name: color for name, color in zip(_color_names, "🔴🟠🟡🟢🔵🟣🟤⚫⚪")}
    colors_square = {name: color for name, color in zip(_color_names, "🟥🟧🟨🟩🟦🟪🟫⬛⬜")}

    @classmethod
    def as_number(cls, number = Union[int, float, str]):
        str_num = str(number)
        str_emoji = ""
        for item in str_num:
            str_emoji += f"{cls.numbers.get(int(item))} "
        return str_emoji