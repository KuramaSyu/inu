from typing import (
    Any,
    Iterable,
    Union,
    List,
    Generator,
)

from .language import Multiple


class StringCutter():
    @staticmethod
    def slice_by_wordcount(string: str,
        cut_at: int = 10,
        seperator: str = ' '
        ) -> List[List[str]]:
        """
        Devides string into multiple Listes with words with a given length.
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
        clean_code: Any = False
        ) -> List[str]:
        """
        Crubles a string into a list with strings which have a given max length.
        """
        if clean_code:
            string.strip()

        sliced_list = __class__.slice_by_length(
            string=string,
            seperator=seperator,
            cut_at=cut_at
        )

        return ["".join(word for word in word_list)
        for word_list in sliced_list]

    @staticmethod
    def slice_by_length(string: str,
        cut_at: int = 1900,
        seperator: str = ' '
        ) -> List[List[str]]:
        """Returns a list with sublists with strings. Sublist total
        stringlength <= cut_at."""

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
        if isinstance(to_iter, str):
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
        self._step

    def __iter__(self):
        return self

    def __next__(self):
        peek = self.peek
        self._step()
        return peek

    def _step(self):
        try:
            self.peek: str = self._gen.__next__()
        except StopIteration:
            self.eof: bool = True


class WordToBig(Exception):
    """
    Raised, when word in iterator is bigger that allowd limit of string len.
    """
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


def crumble(
    string: str,
    max_length_per_string: int = 1900,
    seperator: str = ' ',
    clean_code: bool = True,
    _autochange_seperator = True
    ) -> List[str]:
    """Splits a string into strings which length <= max_length is"""

    if clean_code:
        string = string.strip()

    # some strings only have \n to seperate - not " "
    if seperator == " " and seperator not in string and _autochange_seperator:
        seperator = "\n"
    return StringCutter.crumble(
        string=string,
        cut_at=max_length_per_string,
        seperator=seperator,
        clean_code=clean_code,
    )