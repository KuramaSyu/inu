from typing import *
from collections import Counter
import traceback

class ListParser:
    _separator_order = [
        ";", 
        ",", 
        "->", 
        " "
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
        parses a string into a list of strings.
        The string is checked against separators in `_separator_order`.
        The separator is checked on each line. An item could not be 
        written onto 2 lines
        
        Args:
        -----
        value: str
            the string to parse
            
        Returns:
        --------
        List[str]
            the parsed list
        """
        return self.separate(self._separator_order, value)
        
        
    def separate(self, separator_order: List[str], text: str) -> List[str]:
        """
        Separates the given text into a list of strings based on the provided separator order.

        Args:
        -----
        separator_order: List[str]
            a list of strings that are checked in the given order to separate the text
        text: str
            the text to be separated

        Returns:
        --------
        List[str]
            the separated text
            
        Example:
        --------
        >>> separate([";", ",", " "], "a; b; c")
        ["a", "b", "c"]
        """
        parsed_list: List[str] = []
        for line in text.split("\n"):
            separator = None
            for s in separator_order:
                if s in line:
                    separator = s
                    break
        
            if separator is None and line:
                parsed_list.append(line)
                self._parsed_lines.append((None, [line]))
            else:
                elements = [x for x in line.split(separator) if x]
                parsed_list.extend(elements)
                self._parsed_lines.append((separator, elements))                
            
        return parsed_list
    
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
            parser = cls()
            parser.parse(value)
            counter = Counter([sep for sep, line in parser.parsed_lines for _ in line])
            if sum([value for key, value in counter.items() if key]) >= 4:
                return True
            return False
        except Exception:
            traceback.print_exc()
            
            return False
        
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
    