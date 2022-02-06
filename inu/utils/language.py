import datetime
from re import M
from typing import Sequence, TypeVar, Union, List, Optional, Any

import hikari
from numpy import isin, real
import inspect

T_str_list = TypeVar("T_str_list", str, List[str])

def human_bool(bool_, twisted=False):
    if not twisted:
        return f"{'yes' if bool_ else 'no'}"
    else:
        return f"{'yes' if not bool_ else 'no'}"
def human_time(
        time: datetime.datetime,
        long_: bool = True,
    ):
    if long_:
        day_suffix = "th"
        if time.day == 1:
            day_suffix = "st"
        elif time.day == 2:
            day_suffix = "nd"
        elif time.day == 3:
            day_suffix = "rd"
        return f"""{time.strftime("%A")} the \
                    {time.day}{day_suffix} {time.strftime("%B")}\
                    , {time.year} \
                    ({time.hour}:{time.minute}:{time.second})"""


def opposite(boolean: bool):
    """returns the opposite of the booleaan"""
    return not boolean


class Multiple():
    @staticmethod
    def endswith_(word: str, ends_w: list):
        """returns True, if `word` ends with more than 0 entries of list `ends_w`"""
        for w in ends_w:
            if word.endswith(w):
                return True
        return False

    @staticmethod
    def startswith_(word: str, starts_w: list):
        """returns True, if `word` starts with more than 0 entries of list `ends_w`"""
        for w in starts_w:
            if word.startswith(w):
                return True
        return False


class Human():
    """
    Converts datatypes/other stuff to human readable things.
    Methods named with trailing _ to don't overwrite stuff.
    """

    @staticmethod
    def bool_(boolean, twisted=False):
        if not twisted:
            return f"{'yes' if boolean else 'no'}"
        else:
            return f"{'yes' if not boolean else 'no'}"

    @staticmethod
    def datetime_(
            time: datetime.datetime,
            long_: bool = True,
    ) -> str:
        """
        converts datetime to a long or short readable string.
        Returning datatype is given datatype
        """
        if long_:
            day_suffix = "th"
            if time.day == 1:
                day_suffix = "st"
            elif time.day == 2:
                day_suffix = "nd"
            elif time.day == 3:
                day_suffix = "rd"
            return f"""{time.strftime("%A")} the \
                        {time.day}{day_suffix} {time.strftime("%B")}\
                        , {time.year} \
                        ({time.hour}:{time.minute}:{time.second})"""
        else:
            raise NotImplementedError()

    @staticmethod
    def plural_(
        word_s: T_str_list,
        relation: Union[int, bool, float],
    ) -> T_str_list:
        """ 
        returns a words plural.
        word_s: the word or words with will be converted relating to <relation>
        relation: bool or int -> bool=True == plural; int > 1 = plural
        """
        if isinstance(relation, float):
            relation = True if relation >= 1 else False
        plural = False
        if isinstance(relation, int) and relation > 1:
            plural = True
        elif isinstance(relation, bool):
            plural = relation

        if not plural:
            if isinstance(word_s, list):
                return word_s
            else:
                return [word_s]
        
        def mk_plural(word_s: list) -> List[str]:
            pl_word_s = []
            for w in word_s:
                if Multiple.endswith_(w, ['s', 'ss', 'sh', 'ch', 'x' 'z']):
                    pl_word_s.append(f'{w}es')
                elif Multiple.endswith_(w, ['f', 'fe']):
                    if w.endswith('f'):
                        pl_word_s.append(f'{w[:-2]}ves')
                    else:
                        pl_word_s.append(f'{w[:-3]}ves')
                elif Multiple.endswith_(w, ['y']):
                    if w[-2] in 'aeiou':
                        pl_word_s.append(f'{w[:-2]}ies')
                    else:
                        pl_word_s.append(f'{w}s')
                elif Multiple.endswith_(w, ['o']):
                    pl_word_s.append(f'{w}es')
                elif Multiple.endswith_(w, ['us']):
                    pl_word_s.append(f'{w[:-3]}i')
                elif Multiple.endswith_(w, ['os']):
                    pl_word_s.append(f'{w[:-3]}i')
                elif Multiple.endswith_(w, ['is']):
                    pl_word_s.append(f'{w[:-3]}es')
                else:
                    pl_word_s.append(f'{w}s')
            return pl_word_s

        if isinstance(word_s, list):
            return mk_plural(word_s)
        else:
            return mk_plural([word_s])[0]

    @staticmethod
    def number(number: Union[int, str, float]) -> str:
        """
        Adds commas to <number> every 3 places starting at point or on right side of number
        """
        number = str(number)
        result_number = ""
        index = str.find(number, ".")
        if index != -1:
            result_number += number[index : ][::-1]
            index -= 1
        count = 0

        while True:
            try:
                result_number += number[index]
                count += 1
                index -= 1
                if count % 3 == 0:
                    result_number += ","
                    count = 0
                if index == -1:
                    break
            except Exception:
                break
        if result_number[-1] == ",":
            result_number = result_number[:-1]
        return result_number[::-1]

    @staticmethod
    def short_text(text: Optional[str], max_lengh: int) -> str:
        """
        Returns:
        --------
            - (str) the text until max_lengh with ... or complete text
        """
        if text is None:
            return ""
        if len(text) > max_lengh:
            return f"{text[:max_lengh-3]}..."
        else:
            return text

    @classmethod
    def list_(
        cls,
        list_: Sequence[str],
        wrap_word_with: str = "",
        split_with = ", "
    ):
        """
        ### Converts a list to a more human like list

        Example:
        --------
        Human.list_(["house", "horse", "apple"])
        >>> "a house, a hourse and an apple"

        Returns:
        --------
            - (str) the human like list converted to a str
        """
        result_str = ""
        split_with
        for i, word in enumerate(list_):
            end = ""
            if i < len(list_)-2:
                end = split_with
            elif i == len(list_)-2:
                end = " and "
            result_str += f"{cls.a_or_an(word)} {wrap_word_with}{word}{wrap_word_with}{end}"
        return result_str

    @classmethod
    def a_or_an(cls, word: str):
        """
        Returns:
        -------- 
            - (str) "a" or "an" depending on the word
        """
        if Multiple.startswith_(word, ["a", "e", "i", "o", "u"]):
            return "an"
        return "a"

    @classmethod
    def type_(cls, obj: Any, with_examples: bool = False):
        """
        Args:
        -----
            - obj (Any) the object of which you want to have a readable variant
            - with_examples (bool, default=False) wether or not the return value should have an example

        Returns:
        -------
            - (str) the type but readable and understandable

        Examples:
        --------
             
            >>> Human.type_(12)
            >>> "Number"
            >>> Human.type_(12.3, True)
            >>> "a Number like 42 or 6.9"

        Note:
        -----
            - this is more a `hikari` specific function instead of a general function
        """
        examples = {
            "Discord ID": "362262726191349762",
            "Discord Channel": "#general",
            "Discord User": "@Inu",
            "Number": "42",
            "(point) Number": "42 or 6.9",
            "Text": 'I want to have a RTX 3090'        
        }
        if not isinstance(obj, type):
            obj = obj.__class__
        readable_type = None
        if obj is hikari.Snowflake or issubclass(obj, hikari.Snowflake):
            readable_type = "Discord ID"
        elif obj is int:
            readable_type = "Number"
        elif obj is float:
            readable_type = "(point) Number"
        elif obj is str:
            readable_type = "Text"
        elif obj is hikari.PartialChannel or issubclass(obj, hikari.PartialChannel):
            readable_type = "Discord Channel"
        elif obj is hikari.PartialUser or issubclass(obj, hikari.PartialUser):
            readable_type = "Discord User"
        if not readable_type:
            return obj.__name__
        if readable_type and with_examples:
            return f"{cls.a_or_an(readable_type)} {readable_type} like `{examples[readable_type]}`"
        else:
            return readable_type
        
        

