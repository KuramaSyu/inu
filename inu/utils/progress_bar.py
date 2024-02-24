import time
from typing import *

def pacman(index: int = 0, length: int = 20) -> Generator[str, None, None]:
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
    length = int(length/2)*2
    while True:
        index = index % (length * 2)
        C = "C" if index % 2 == 0 else "c"
        space = " " if index % 4 in [2,3] else ""
        rest = (length - index//2) // 2
        yield f"[{index//2 * '-'}{C}{space}{rest * 'ο '}]"
        index += 1

if __name__ == "__main__":
    gen = pacman(5, 20)
    for i in range(100):
        print(gen.__next__())
        time.sleep(0.2)