import typing
from typing import Sequence

GridLike = Sequence[Sequence]

class Grid:
    """
    Class with class methods for a grid/matrix
    
    https://stackoverflow.com/questions/6313308/get-all-the-diagonals-in-a-matrix-list-of-lists-in-python
    """
    @classmethod
    def get_backward_diagonals(cls, grid: GridLike):
        b = [None] * (len(grid) - 1)
        grid = [b[i:] + r + b[:i] for i, r in enumerate(cls.get_rows(grid))]
        return [[c for c in r if c is not None] for r in cls.get_cols(grid)]

    @classmethod
    def get_forward_diagonals(cls, grid: GridLike):
        b = [None] * (len(grid) - 1)
        grid = [b[:i] + r + b[i:] for i, r in enumerate(cls.get_rows(grid))]
        return [[c for c in r if c is not None] for r in cls.get_cols(grid)]
    
    @classmethod
    def get_rows(cls, grid: GridLike):
        return [[c for c in r] for r in grid]

    @classmethod
    def get_cols(cls, grid: GridLike):
        return zip(*grid)