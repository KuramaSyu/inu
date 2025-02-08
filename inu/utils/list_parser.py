from typing import *
from collections import Counter
import traceback
from abc import ABC, abstractmethod
import re

from hikari import PartialChannel


class ListStrategy(ABC):
    def __init__(self, content: str):
        self._content = content
        self._bare: List[str] = []
        self._processed: List[str] = []
    
    def is_usable(self) -> bool:
        ...
    
    @abstractmethod
    def parse(self) -> List[str]:
        ...
    
    @property
    @abstractmethod
    def count(self) -> int:
        ...
    
    @property
    def processed_list(self) -> List[str]:
        """
        Contains list removed of enumeration or bullet points
        """
        if not self._processed:
            self.parse()
        return self._processed

    @property
    def bare_list(self) -> List[str]:
        """
        Contains list with enumeration or bullet points
        """
        if not self._bare:
            self.parse()
        return self._bare

    @abstractmethod
    def reassemble(self, new_list: List[str]) -> str:
        ...


class MarkDownStrategy(ListStrategy, ABC):
    @property
    @abstractmethod
    def regex(self) -> str:
        ...

    def is_usable(self) -> bool:
        if len(self._content.splitlines()) < 2:
            return False
        return all(re.match(self.regex, line) for line in self._content.splitlines() if line)

    def parse(self) -> List[str]:
        if self._bare:
            return self._bare
        for line in self._content.splitlines():
            if not line:
                continue
            self._processed.append(
                re.sub(self.regex, "", line).strip()
            )
            self._bare.append(line)
        return self._bare

    @property
    def count(self) -> int:
        if not self._bare:
            self.parse()
        return len(self._bare)


class EnumerationMarkdownStrategy(MarkDownStrategy):
    @property
    def regex(self) -> str:
        return r"^\s*\d+\.?\s*"

    @property
    def weight(self) -> int:
        return 10

    def reassemble(self, new_list: List[str]) -> str:
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(new_list))


class MarkdownListStrategy(MarkDownStrategy):
    @property
    def regex(self) -> str:
        return r"^\s*[-*][ ]+\s*"  # Checks for bullet point followed by at least one character

    @property
    def count(self) -> int:
        if not self._bare:
            self.parse()
        return len(self._bare)
    
    @property
    def weight(self) -> int:
        return 9

    def reassemble(self, new_list: List[str]) -> str:
        return "\n".join(f"- {item}" for item in new_list)

class SimpleStringSplitStrategy(ListStrategy):
    def __init__(self, content: str, separator: str):
        super().__init__(content)
        self._separator = separator
    
    def is_usable(self) -> bool:
        # The strategy is usable if the separator appears in the content.
        return self._separator in self._content and len(self._content.split(self._separator)) > 1
    
    def parse(self) -> List[str]:
        if self._bare:
            return self._bare
        self._processed = [part.strip() for part in self._content.split(self._separator) if part.strip()]
        self._bare = [part for part in self._content.split(self._separator) if part]
        return self._bare
    
    @property
    def weight(self) -> int:
        sep_weights = {"\n": 8, ";": 7, ",": 6, "->": 5}
        return sep_weights.get(self._separator, 0)

    @property
    def count(self) -> int:
        if not self._bare:
            self.parse()
        return len(self._bare)

    def reassemble(self, new_list: List[str]) -> str:
        return self._separator.join(new_list)



class ListParser:
    _separator_order = [
        "; ",
        ";", 
        ", ",
        ",", 
        "->", 
        "\n",
    ]
    
    def __init__(self):
        self._parsed_lines: List[Tuple[str, List[str]]] = []
        
    @property
    def parsed_lines(self) -> List[Tuple[str, List[str]]]:
        """
        List with Tuples containing the separator and the parsed lines
        """
        return self._parsed_lines

    def parse(self, value: str) -> ListStrategy:
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
        processed: bool
            whether the return list will be processed (e.g. 1. 2. 3. or - at start of line stripped)
            
        Returns:
        --------
        List[str]
            the parsed list
        """
        strategy = None
        # try strategies in order
        candidate = EnumerationMarkdownStrategy(value)
        if candidate.is_usable():
            strategy = candidate
        else:
            candidate = MarkdownListStrategy(value)
            if candidate.is_usable():
                strategy = candidate
            else:
                for sep in self._separator_order:
                    candidate = SimpleStringSplitStrategy(value, sep)
                    if candidate.is_usable():
                        strategy = candidate
                        break
        print(f"use strategy: {strategy}")
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
        return strategy
    
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
1. ICE-Spikes Biom finden,  
2. Zombie Doktor Achievment (difficulty hard),  
3. Silk Touch auf Tool oder Buch,  
4. Hot Tourist Destination,  
5. 5 Effekte Gleichzeitig,  
6. RAID abschließen (Hero of the village),  
7. Eins der 3 Sachen mit Fernglas anschauen,  
8. Caves and Cliffs als erstes (von oben nach unten).
"""
    false_string = "1,2,3,4,5,6"
    print(ListParser().parse(test_string))
    print(ListParser().check_if_list(test_string))
    print(ListParser().check_if_list(false_string))
