import typing
from typing import List, List, Tuple, Iterable, TypeVar, Union

T = TypeVar("T")

class Grid:
    """
    Class with class methods for a grid/matrix
    
    https://stackoverflow.com/questions/6313308/get-all-the-diagonals-in-a-matrix-list-of-lists-in-python
    """
    @classmethod
    def get_backward_diagonals(cls, grid: List[List[T]]) -> List[List[T]]:
        b = [None] * (len(grid) - 1)
        new_grid = [[*b[i:], *r, *b[:i]] for i, r in enumerate(cls.get_rows(grid))]
        return [[c for c in r if c is not None] for r in cls.get_cols(new_grid)]

    @classmethod
    def get_forward_diagonals(cls, grid: List[List[T]]) -> List[List[T]]:
        b = [None] * (len(grid) - 1)
        rows = cls.get_rows(grid)
        new_grid = [[*b[:i], *r, *b[i:]] for i, r in enumerate(rows)]
        return [[c for c in r if c is not None] for r in cls.get_cols(new_grid)]
    
    @classmethod
    def get_rows(cls, grid: List[List[T]]) -> List[List[T]]:
        return [[c for c in r] for r in grid]

    @classmethod
    def get_cols(cls, grid: List[List[T]]) -> List[Tuple[T]]:
        return [*zip(*grid)]  ##type ignore
