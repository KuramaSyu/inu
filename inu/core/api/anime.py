from typing import *



class PartialAnimeMatch(TypedDict):
    rank: int
    rank_suffix: str
    name: str
    score: float

class AnimeMatch(PartialAnimeMatch):
    rank: int
    rank_suffix: str
    name: str
    score: float
    mal_id: int