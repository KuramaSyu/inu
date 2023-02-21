from sys import maxsize
from typing import (
    Any,
    Iterable,
    Optional,
    Union,
    List,
    Generator,
)

# from .language import Multiple


class StringCutter():
    @staticmethod
    def slice_by_wordcount(
        string: str,
        cut_at: int = 10,
        seperator: str = ' '
        ) -> List[List[str]]:
        """
        Devides string into multiple Lists with words with a given length.
        """
        string_list = [[]]

        [string_list[-1].append(word) 
        if len(string_list[-1]) < cut_at or not cut_at
        else string_list.append([word]) 
        for word in string.split(seperator)]

        return string_list

    @staticmethod
    def crumble(string: str,
        cut_at: int = 1900,
        seperator: str = ' ',
        ) -> List[str]:
        """
        Crubles a string into a list with strings which have a given max length.
        """
        sliced_list = __class__.slice_by_length(
            string=string,
            seperator=seperator,
            cut_at=cut_at
        )

        return ["".join(word for word in word_list)
        for word_list in sliced_list]

    @staticmethod
    def slice_by_length(
        string: Union[List[str], str],
        cut_at: int = 1900,
        seperator: str = ' '
    ) -> List[List[str]]:
        """
        Args:
        -----


        Returns:
        --------
        - (`List[List[str]]`) a list with sublists with strings. Sublist total
          stringlength <= cut_at.
        """

        list_length = 0
        word_list = []
        i = PeekIterator(string, seperator=seperator)

        while not i.eof:
            word_list.append([])
            list_length = 0
            if len(i.peek) > cut_at:
                raise WordToBig(
                    f'''Word in iterable was bigger ({len(i.peek)}) 
                    than the max given string lenth ({cut_at})'''
                )

            while ((list_length := list_length + len(i.peek)) <= cut_at 
                and not i.eof):
                word_list[-1].append(next(i))

        return word_list

class PeekIterator():
    """Iterator with 1 peak look ahead with peek atribute"""

    def __init__(self, 
        to_iter: Union[str, List[str]], 
        seperator: str = ' '
        ) -> None:
        if isinstance(to_iter, list):
            self._gen = (item if item else '' for item in to_iter)
        elif isinstance(to_iter, str):
            def generator(to_iter: str = to_iter, seperator: str = seperator) -> Generator[str, None, None]:
                for item in str(to_iter).split(seperator):
                    if not item:
                        yield ''
                    elif len(item) > 2000:
                        generator(item)
                    else:
                        yield item
            self._gen = generator()
            #self._gen = (f"{item}{seperator}" if item and len(item) < 2000 else '' if not item else sub_item if sub_item else '' for sub_item in crumble(item, 1980) for item in to_iter.split(seperator))
        
        self.peek = ''
        self.eof = False
        self._step()

    def __iter__(self):
        return self

    def __next__(self):
        peek = self.peek
        if self.eof:
            raise StopIteration()
        self._step()
        return peek

    def _step(self):
        try:
            self.peek: str = self._gen.__next__()
        except StopIteration:
            self.eof: bool = True

class SentenceInterator():
    """Returns strings with max size <max_size> intelligent splited."""

    def __init__(self, 
        to_iter: Union[str, List[str]], 
        max_size: int = 2000,
        ) -> None:
        if isinstance(to_iter, list):
            self._gen = (item if item else '' for item in to_iter)
        elif isinstance(to_iter, str):
            def generator(
                max_size:int = max_size,
                to_iter: str = to_iter,
            ) -> Generator[str, None, None]:
                """
                Iterates intelligent over the sentence

                Yields: Substrngs of this sentence
                
                """
                pos: int = 0
                symbols = ["\n\n\n", "\n\n", "\n", ";", ". ", "? ", "! ", ",", ") ", "} ", "] " ,": ", " ", ""]
                while pos + max_size < len(to_iter):
                    subitem = to_iter[pos:pos+max_size]
                    for symbol in symbols:
                        # nothing found -> look for lower prio symbol
                        if (
                            (occurence := subitem.rfind(symbol)) == -1
                            or occurence < max_size / 3 * 2
                        ):
                            
                            continue 
                        # smth found -> update pos, go to next substring
                        else:
                            # optimise if something paragraph like is detected - not necessary for code
                            # this will prevent from something like <title>\n\n\n<entry> whill be cutted after title
                            if (
                                ("\n" in symbol or "\n" == symbol)
                                # there is another \n in the string
                                and (sub_occurence := subitem[:occurence-len(symbol)].rfind("\n")) != -1
                                # other \n under the last 45 chars (these 45 are most likely the next paragraph headline)
                                and sub_occurence > len(subitem[:occurence-len(symbol)])-45
                            ):
                                # the suboccurence is not to short
                                if sub_occurence < occurence / 4 * 3:
                                    continue
                                # new phrase detected -> starting next iter with new phrase
                                yield subitem[:sub_occurence]
                                pos = pos + sub_occurence + len(symbol)
                                break
                            else:
                                yield subitem[:occurence+len(symbol)]
                                pos = pos + occurence + len(symbol)
                                break
                yield to_iter[pos:]

            self._gen = generator(
                to_iter=to_iter,
                max_size=max_size
            )
            #self._gen = (f"{item}{seperator}" if item and len(item) < 2000 else '' if not item else sub_item if sub_item else '' for sub_item in crumble(item, 1980) for item in to_iter.split(seperator))
        
        self.peek = ''
        self.eof = False
        self._step

    def __iter__(self):
        return self

    def __next__(self):
        # peek = self.peek
        # self._step()
        # return peek
        return self._gen.__next__()

    def _step(self):
        try:
            self.peek: str = self._gen.__next__()
        except StopIteration:
            self.eof: bool = True

class WordIterator:
    """
    ### Iterates through a string <`to_iter`> and returns word for word 
    """

    def __init__(self, 
        to_iter: str, 
    ) -> None:
        self.to_iter = to_iter
        self._gen = (word for word in to_iter.split(" "))

    def __iter__(self):
        return self

    def __next__(self):
        # don't return value instantly
        # add the removed whitespace for splitting to it
        return f"{self._gen.__next__()} "


class NumberWordIterator:
    """
    Iterator with 1 peak look ahead with peek atribute

    Example:
    -------
    "12.34House123 21bac12.12.12.12"
    >>> 12.34
    >>> House
    >>> 123
    >>> 21
    >>> bac
    >>> 12.12
    >>> 0.12
    >>> 0.12
    """

    def __init__(self, 
        to_iter: str, 
        ) -> None:
            self.to_iter = to_iter.lower()
            self._gen = (c for c in to_iter)
            self.eof = False
            try:
                self.peek_char = self._gen.__next__()
            except:
                self.eof = True
            self.peek_index = 1
            self.index = 0
            self.last_word_index = 0
            self.peek: str = ''

            self._step()
            

    def __next_incr(self) -> str:
        self.peek_char = self._gen.__next__()
        self.peek_index += 1
        return self.peek_char

    def __iter__(self):
        return self

    def __next__(self):
        peek = self.peek
        self.last_word_index = self.index
        self.index = self.peek_index
        self._step()
        if peek is None:
            raise StopIteration
        return peek

    def _next_number(self, prefix: str = "") -> float:
        number_chars = "1234567890-.,"
        number = prefix
        number = number.replace(",", ".")
        if "." in number:
            has_point = True
        else:
            has_point = False
        while self.peek_char in number_chars:
            if self.peek_char == " ":
                self.peek_char: str = self.__next_incr()
                break
            if self.peek_char == "-" and number != "":
                break
            if self.peek_char in ".,":
                if has_point:
                    break
                else:
                    number += self.peek_char
                    has_point = True
            else:
                number += self.peek_char
            try:
                self.peek_char: str = self.__next_incr()
            except StopIteration:
                self.eof = True
                break
        number = number.replace(",", ".")
        if number.startswith("."):
            number = f"0{number}"
        try:
            number = float(number)
        except Exception:
            raise RuntimeError(f"Can't parse `{number}` to float")
        return number

    def _next_word(self, prefix: str = "") -> str:
        number_chars = "1234567890"
        word = prefix
        while not self.peek_char in number_chars:
            if self.peek_char == " ":
                self.peek_char: str = self.__next_incr()
                break
            word += self.peek_char
            try:
                self.peek_char: str = self.__next_incr()
            except StopIteration:
                self.eof = True
                break
        return word

    def _step(self):
        number_chars = "1234567890"
        number_prefix = ".,-"
        if self.eof:
            self.peek = None
            return
        if self.peek_char in number_chars:
            self.peek = self._next_number()
        elif self.peek_char in number_prefix:
            peek = self.peek_char
            peek_peek = self.peek_char = self._gen.__next__()
            self.index += 1
            if peek_peek in number_chars:
                self.peek = self._next_number(prefix=peek)
            else:
                self.peek = self._next_word(prefix=peek)
        else:
            self.peek = self._next_word()

    


class WordToBig(Exception):
    """
    Raised, when word in iterator is bigger that allowd limit of string len.
    """
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


    @staticmethod
    def slice_by_length(
        string: Union[List[str], str],
        cut_at: int = 1900,
        seperator: str = ' '
    ) -> List[List[str]]:
        """
        Args:
        -----
        string : `str`
            the string you want to cut into lists
        cut_at : `int`
            how long the partial strings should be
        seperator : `str`
            the seperator, where to cut the <string> if not list
 
        Returns:
        --------
        `List[str]` :
            a List with strings with max length <= `<cut_at>`
        """
        word_list = StringCutter.slice_by_length(
            string=string,
            cut_at=cut_at,
            seperator=seperator,
        )
        return [seperator.join(l) for l in word_list]

def crumble(
    text: str | List[str],
    max_length_per_string: int = 2000,
    seperator: Optional[str] = None,
    clean_code: bool = True,
    _autochange_seperator = True,
) -> List[str]:
    """
    Splits a string into strings which length <= max_length is. If seperator is None, 
    more intelligent splitting will be userd. If a list is passed in, every item will
    start with a new string in the returning list.
    
    Args:
    -----
    `text : str | List[str]`
        The string which should be crumbled
    `max_length_per_string : int`
        The maximum length per string in the return list. 
        Default: 2000
    `seperator : str | None`
        The seperator where to cut the string.
        Default: None
        If None, then the string will be cutted more human likely
    `clean_code : bool`
        strip string and post corrects code blocks.
        Default: True
    `_autochange_seperator : bool`
        If seperator is not present, then seperator will be changed to `\n`.
        Default: True

    Returns:
    --------
    List[str] :
        A list with strings with len <= <max_length_per_string>
    
    """
    crumbled_string: List[str] = []
    bare_strings = text if isinstance(text, list) else [text] 

    if clean_code:
        bare_strings = [text.strip() for text in bare_strings]

    
    if any([True for text in bare_strings if len(text) <= max_length_per_string]):
        return bare_strings
    
        # some strings only have \n to seperate - not " "
    if (
        seperator 
        and seperator not in text 
        and _autochange_seperator
    ):
        seperator = "\n"

        for text in bare_strings: 
            crumble_string = StringCutter.crumble(
                string=text,
                cut_at=max_length_per_string,
                seperator=seperator,
            )
            crumbled_string.extend(crumble_string)
    else:
        for text in bare_strings:
            crumble_string = [part for part in SentenceInterator(text, max_length_per_string)]
            crumbled_string.extend(crumble_string)
    
    if not clean_code:
        return crumbled_string
    else:
        corrected_strings: List[str] = []
        for text in crumbled_string:
            # string has starting code block but was cut
            if text.count("```") % 2 != 0:
                text += "\n```"
            corrected_strings.append(text)
        return corrected_strings
    




