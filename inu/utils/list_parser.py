from typing import *
from collections import Counter
import traceback
from abc import ABC, abstractmethod
import re


class ListStrategy(ABC):
    def __init__(self, content: str):
        self._content = content
        self._parsed: List[str] = []
    
    def is_usable(self) -> bool:
        ...
    
    @abstractmethod
    def parse(self) -> List[str]:
        ...
    
    @property
    @abstractmethod
    def count(self) -> int:
        ...

class MarkDownStrategy(ListStrategy, ABC):
    @property
    @abstractmethod
    def regex(self) -> str:
        ...


class EnumerationMarkdownRegex(MarkDownStrategy):
    @property
    def regex(self) -> str:
        return r"^[ ]*\d+[.]?.+"
    
    def is_usable(self) -> bool:
        if len(self._content.splitlines()) < 2:
            return False
        return all(re.match(self.regex, line) for line in self._content.splitlines())

    def parse(self) -> List[str]:
        if self._parsed:
            return self._parsed
        for line in self._content.splitlines():
            self._parsed.append(
                re.sub(self.regex, "", line)
            )
        return self._parsed

    @property
    def count(self) -> int:
        if not self._parsed:
            self.parse()
        return len(self._parsed)
    
    @property
    def weight(self) -> int:
        return 10

class ListMarkdownRegex(MarkDownStrategy):
    @property
    def regex(self) -> str:
        return r"^[ ]*[-*].+"
    
    def is_usable(self) -> bool:
        if len(self._content.splitlines()) < 2:
            return False
        return all(re.match(self.regex, line) for line in self._content.splitlines())

    def parse(self) -> List[str]:
        if self._parsed:
            return self._parsed
        for line in self._content.splitlines():
            self._parsed.append(
                re.sub(self.regex, "", line)
            )
        return self._parsed

    @property
    def count(self) -> int:
        if not self._parsed:
            self.parse()
        return len(self._parsed)
    
    @property
    def weight(self) -> int:
        return 9

class SimpleStringSplitStrategy(ListStrategy):
    def __init__(self, content: str, separator: str):
        super().__init__(content)
        self._separator = separator
    
    def is_usable(self) -> bool:
        # The strategy is usable if the separator appears in the content.
        return self._separator in self._content
    
    def parse(self) -> List[str]:
        if self._parsed:
            return self._parsed
        self._parsed = [part.strip() for part in self._content.split(self._separator) if part.strip()]
        return self._parsed
    
    @property
    def weight(self) -> int:
        sep_weights = {"\n": 8, ";": 7, ",": 6, "->": 5, " ": 4}
        return sep_weights.get(self._separator, 0)

    @property
    def count(self) -> int:
        if not self._parsed:
            self.parse()
        return len(self._parsed)


class ListParser:
    _separator_order = [
        ";", 
        ",", 
        "->", 
        "\n",
        " ",
    ]
    
    def __init__(self):
        self._parsed_lines: List[Tuple[str, List[str]]] = []
        
    @property
    def parsed_lines(self) -> List[Tuple[str, List[str]]]:
        """
        List with Tuples containing the separator and the parsed lines
        """
        return self._parsed_lines

    def parse(self, value: str) -> List[str]:
        """
        parses a string into a list of strings using strategies.
        Check from top to down: 
         1. EnumerationMarkdownRegex (weight 10)
         2. ListMarkdownRegex (weight 9)
         3. SimpleStringSplitStrategy for each separator in order:
            "\n" (8), ";" (7), "," (6), "->" (5), " " (4)
        
        Args:
        -----
        value: str
            the string to parse
            
        Returns:
        --------
        List[str]
            the parsed list
        """
        strategy = None
        # try strategies in order
        candidate = EnumerationMarkdownRegex(value)
        if candidate.is_usable():
            strategy = candidate
        else:
            candidate = ListMarkdownRegex(value)
            if candidate.is_usable():
                strategy = candidate
            else:
                for sep in ["\n", ";", ",", "->", " "]:
                    candidate = SimpleStringSplitStrategy(value, sep)
                    if candidate.is_usable():
                        strategy = candidate
                        break
        
        if strategy is None:
            raise ValueError("No strategy (markdown enumeration, markdown list, simple strings) found to parse the given string.")
        parsed = strategy.parse()
        # Identify the strategy by its regex (for markdown ones) or by the splitting string.
        if isinstance(strategy, MarkDownStrategy):
            identifier = strategy.regex
        elif isinstance(strategy, SimpleStringSplitStrategy):
            identifier = strategy._separator
        else:
            identifier = ""
        self._parsed_lines = [(identifier, parsed)]
        return parsed
    
    @classmethod
    def check_if_list(cls, value: str) -> bool:
        """
        Checks if the given string is a list.

        Args:
        -----
        cls: class
            The class object.
        value: str
            The string to check.

        Returns:
        --------
        bool
            True if the string is a list, False otherwise.
        """
        try:
            ListParser().parse(value)
        except ValueError:
            return False
        return True
        
    @property
    def count_seperators(self) -> Counter:
        return Counter([sep for sep, line in self.parsed_lines for _ in line])
            
    

if __name__ == "__main__":
    test_string = """
a; b; c
1,2,3
3,4; 5,6
a
b
"""
    false_string = "1,2,3,4,5,6"
    print(ListParser().parse(test_string))
    print(ListParser().check_if_list(test_string))
    print(ListParser().check_if_list(false_string))
