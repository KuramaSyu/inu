import time
from typing import *

def pacman(index: int = 0, length: int = 20, short: bool = False, increment: int = 1) -> Generator[str, None, None]:
    """
    A generator that yields a string of a pacman animation.
    
    Args:
    index: int
        the index of the animation. Max index is length * 2.
    length: int
        the length of the animation. It must be even.
        
    Yields:
    str:
        a string of the animation.
    """
    length = int(length / 2) * 2
    floor_div = 1 if short else 2
    while 1:
        index = index % (length * floor_div)
        C = "C" if index % 2 == 0 else "c"
        space = " " if index % 4 in [2,3] else ""
        if short:
            space = " " if index % 2 == 1 else ""
        rest = (length - index // floor_div) // 2
        yield f"[{index // floor_div * '-'}{C}{space}{rest * 'ο '}]"
        index += increment

if __name__ == "__main__":
    gen = pacman(5, 20, False)
    gen2 = pacman(5, 20, True, 3)
    for i in range(100):
        print(gen.__next__())
        print(gen2.__next__())
        time.sleep(0.2)