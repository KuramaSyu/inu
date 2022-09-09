import datetime
from typing import *
from enum import Enum
import yaml
import random
import os

import hikari
from numpy import isin, real
import inspect
import textwrap
from pprint import pprint

from utils import WordIterator
from core import getLogger, SectionProxy

T_str_list = TypeVar("T_str_list", str, list)

log = getLogger(__name__)

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
    def endswith_(word: str, ends_w: list) -> str:
        """returns the char or "", if `word` ends with more than 0 entries of list `ends_w`"""
        for w in ends_w:
            if word.endswith(w):
                return w
        return ""

    @staticmethod
    def startswith_(word: str, starts_w: list) -> str:
        """returns the char or "", if `word` starts with more than 0 entries of list `ends_w`"""
        word = str(word)
        for w in starts_w:
            if word.startswith(str(w)):
                return w
        return ""
    
    @staticmethod
    def repalce_(text: str, symbols: Iterable, with_: str):
        for symbol in symbols:
            text = text.replace(symbol, with_)
        return text


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
        with_number: bool = False,
    ) -> T_str_list:
        """ 
        returns
            - (str) a word/s plural.
        word_s: the word or words with will be converted relating to <relation>
        relation: bool or int -> bool=True == plural; int > 1 = plural,
        with_number (bool) wether or not to put relation before the word when it is int or float
        """
        if with_number:
            if not isinstance(relation, (int, float)):
                with_number = False
        plural = False
        if isinstance(relation, float) and relation != 1:
            plural = True
        
        if isinstance(relation, int) and relation > 1 or relation == 0:
            plural = True
        elif isinstance(relation, bool):
            plural = relation 

        if not plural:
            if isinstance(word_s, list):
                if with_number:
                    return [f"{relation} {w}" for w in word_s]
                else:
                    return word_s
            else:
                if with_number:
                    return f"{relation} {word_s}"
                else:
                    return word_s
        
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
            words = mk_plural(word_s)
            if with_number:
                return [f"{relation} {w}" for w in word_s]
            else:
                return words
        else:
            entry = mk_plural([word_s])[0]
            if with_number:
                return f"{relation} {entry}"
            else:
                return entry

    @staticmethod
    def number(number: Union[int, str, float]) -> str:
        """
        Add commas to an integer `n`.

            >>> commify(1)
            '1'
            >>> commify(123)
            '123'
            >>> commify(1234)
            '1,234'
            >>> commify(1234567890)
            '1,234,567,890'
            >>> commify(123.0)
            '123.0'
            >>> commify(1234.5)
            '1,234.5'
            >>> commify(1234.56789)
            '1,234.56789'
            >>> commify('%.2f' % 1234.5)
            '1,234.50'
            >>> commify(None)
            >>>

        """
        SEPERATOR = "'"
        if isinstance(number, int):
            return f"{number:,d}"
        number = str(number)
        if '.' in number:
            dollars, cents = number.split('.')
        else:
            dollars, cents = number, None

        r: List[Any] = []
        for i, c in enumerate(str(dollars)[::-1]):
            if i and (not (i % 3)):
                r.insert(0, SEPERATOR)
            r.insert(0, c)
        out = ''.join(r)
        if cents:
            out += '.' + cents
        if "." in out:
            while out.endswith("0"):
                # remove trailing zeros
                out = out[:-1]
            # remove dot if dot is the last character
            if out.endswith("."):
                out = out[:-1]
        return out

    @staticmethod
    def short_text(text: Optional[str], max_lengh: int) -> str:
        """
        Returns:
        --------
            - (str) the text until max_lengh with ... or complete text
        """
        text = str(text)
        if len(text) <= max_lengh:
            return text
        suffix = " [...]"
        short_text = ""
        for word in WordIterator(text):
            if len(short_text) + len(word) + len(suffix) < max_lengh:
                short_text += word
            else:
                short_text += suffix
                break
        return short_text

    @staticmethod
    def short_text_from_center(text: Optional[str], max_length: int) -> str:
        """
        Returns:
        --------
            - (str) the text until max_lengh with ... or complete text
        """
        text = str(text)
        if len(text) <= max_length:
            return text
        suffix = " [...] "
        max_length = int(max_length - len(suffix))
        return f"{text[:int(max_length/2)]}{suffix}{text[-1*(int(max_length/2)):]}"

    @classmethod
    def list_(
        cls,
        list_: Sequence[str],
        wrap_word_with: str = "",
        before_word: str = "",
        after_word: str = "",
        with_a_or_an: bool = True,
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
            result_str += f"{cls.a_or_an(word) if with_a_or_an else ''} {before_word}{wrap_word_with}{word}{wrap_word_with}{after_word}{end}"
        return result_str

    @classmethod
    def a_or_an(cls, word: str):
        """
        Returns:
        -------- 
            - (str) "a" or "an" depending on the word
        """
        if Multiple.startswith_(word.lower(), ["a", "e", "i", "o", "u"]):
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
class Languages(Enum):
    EN: str = "en"
    DE: str = "de"
    FR: str = "fr"
    ES: str = "es"
    IT: str = "it"
    PT: str = "pt"
    NL: str = "nl"

class MultilangProxy:
    def __init__(
        self,
        section_name: str, 
        section_options: Union[List[Any], Dict[str, Any]],
        lang: Languages,
        path: str,
        case_insensitive: bool = True,
        

    ):
        """
        Represents one Section of a `config.[yaml|ini]` file

        NOTE:
        -----
            - __getattr__ is case insensitive
        """
        self._path = path
        self.lang = lang
        self.case_insensitive = case_insensitive
        if isinstance(section_options, list):
            section_options = {section_name: section_options}
        self.name = section_name
        self.options = {}
        for key, value in section_options.items():
            if isinstance(value, dict):
                self.options[str(key)] = self._dict_to_section_proxy(key, value)
            else:
                self.options[str(key)] = value
        if self.case_insensitive:
            self.options = {k.lower(): v for k, v in self.options.items()}

    def __getattr__(self, name: str) -> str:
        name = name.lower()
        result = self.options.get(name, None)
        if result is None:
            raise AttributeError(f"config section: `{self.name}` has no attribute `{name}`")
        return result

    def __repr__(self):
        return f"<`{self.__class__.__name__}` section:{self.name}; attrs: {self.options}>"

    @property
    def path(self):
        return f"{self._path}/~.{self.name}"


    def _dict_to_section_proxy(self, key: str, d: dict):
        return self.__class__(key, d, self.lang, self.path, self.case_insensitive)

    def add_sub_proxy(self, sub_proxy: "MultilangProxy"):
        self.options[sub_proxy.name] = sub_proxy

    def get(self, path: str, append_language: bool = True) -> Any:
        """get the coresponding object to the path
        
        Parameters:
        -----------
        path: str
            a path like `picture_guessing/title` to the object in the yaml file
        append_language: bool
            wether or not to append the language to the path like `picture_guessing/title/en`
        """
        if append_language:
            path = f"{path}/{self.lang.value}"
        parts = path.split("/")
        part = parts[0]
        rest_parts = parts[1:]
        try:
            obj = self.options[part]
        except KeyError:
            raise KeyError(f"{self.name} has no attribute `{part}`")
        if isinstance(obj, self.__class__):
            return obj.get("/".join(rest_parts), append_language=False)  # only append lang once
        else:
            return obj




class MultiLang:
    def __init__(
        self,
        guild_id: int,
        multilang_folder: str,
        lang: Languages = Languages.EN
    ):
        self.guild_id = guild_id
        self._folder = multilang_folder
        self.lang = lang
        self._load()
        self._base_path = "/inu/data/multilang"
        self._yaml: Dict[str, Any] = {}
        self._proxy = self.yaml_config()

    def _load(self):
        """loads all yaml files form `self.path` and updates `self._yaml` with its value"""
    
    async def fetch_lang(self):
        pass

    def get_proxy(self):
        return self._proxy



    @property
    def path(self):
        return f"{os.getcwd()}/{self._base_path}/{self._folder}"

    def yaml_config(self, path: Optional[str] = None) -> MultilangProxy:
        if path is None:
            path = self.path
        stream = ""

        def resolve_proxies(full_path: str, root_proxy: MultilangProxy) -> MultilangProxy:
            """
            Returns:
            --------
                - (list) a list of all yaml files in the given path              
            """
            files = []
            for f in os.listdir(full_path):
                if f.endswith(".yaml"):
                    files.append(f)
                    with open(f"{full_path}/{f}", "r", encoding="utf-8") as y:
                        stream = y.read()
                    config = yaml.load(stream, Loader=yaml.CLoader)
                    for sub_proxy in [
                        MultilangProxy(k, v, self.lang, self.path) 
                        for k, v in config.items()
                    ]:
                        root_proxy.add_sub_proxy(sub_proxy)

                elif os.path.isdir(f"{full_path}/{f}"):
                    sub_proxy = MultilangProxy(f, {}, root_proxy.lang, root_proxy.path ,root_proxy.case_insensitive)
                    sub_proxy = resolve_proxies(f"{full_path}/{f}", sub_proxy)
                    root_proxy.add_sub_proxy(sub_proxy)
            return root_proxy

        last_node = path.split("/")[-1]
        root_proxy = MultilangProxy(section_name=last_node, section_options={}, lang=self.lang, path=path)
        resolve_proxies(path, root_proxy)
        return root_proxy

    def __repr__(self) -> str:
        return f"<`{self.__class__.__name__}` {self._proxy}>"


        
        

if __name__ == "__main__":
    print(Human.number("1200000"))