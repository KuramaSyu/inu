import datetime
from typing import Union, List

def human_bool(bool_, twisted=False):
    if not twisted:
        return f"{'yes' if bool_ else 'no'}"
    else:
        return f"{'yes' if not bool_ else 'no'}"
def human_time(
        time: datetime.datetime,
        long_: bool = True,
    ):
    if long_:
        day_suffix = "th"
        if time.day == 1:
            day_suffix = "st"
        elif time.day == 2:
            day_suffix = "nd"
        elif time.day == 3:
            day_suffix = "rd"
        return f"""{time.strftime("%A")} the \
                    {time.day}{day_suffix} {time.strftime("%B")}\
                    , {time.year} \
                    ({time.hour}:{time.minute}:{time.second})"""


def opposite(boolean: bool):
    """returns the opposite of the booleaan"""
    return not boolean


class Multiple():
    @staticmethod
    def endswith_(word: str, ends_w: list):
        """returns True, if `word` ends with <0 entries of list `ends_w`"""
        for w in ends_w:
            if word.endswith(w):
                return True
        return False


class Human():
    """
    Converts datatypes/other stuff to human readable things.
    Methods named with trailing _ to don't overwrite stuff.
    """

    @staticmethod
    def bool_(boolean, twisted=False):
        if not twisted:
            return f"{'yes' if boolean else 'no'}"
        else:
            return f"{'yes' if not boolean else 'no'}"

    @staticmethod
    def datetime_(
            time: datetime.datetime,
            long_: bool = True,
    ) -> str:
        """
        converts datetime to a long or short readable string.
        Returning datatype is given datatype
        """
        if long_:
            day_suffix = "th"
            if time.day == 1:
                day_suffix = "st"
            elif time.day == 2:
                day_suffix = "nd"
            elif time.day == 3:
                day_suffix = "rd"
            return f"""{time.strftime("%A")} the \
                        {time.day}{day_suffix} {time.strftime("%B")}\
                        , {time.year} \
                        ({time.hour}:{time.minute}:{time.second})"""
        else:
            raise NotImplementedError()

    @staticmethod
    def plural_(
        word_s: Union[str, list],
        relation: Union[int, bool],
    ) -> List[str]:
        """ 
        returns a words plural.
        word_s: the word or words with will be converted relating to <relation>
        relation: bool or int -> bool=True == plural; int > 1 = plural
        """
        plural = False
        if isinstance(relation, int) and relation > 1:
            plural = True
        elif isinstance(relation, bool):
            plural = relation

        if not plural:
            if isinstance(word_s, list):
                return word_s
            else:
                return [word_s]
        
        def mk_plural(word_s: list) -> List[str]:
            pl_word_s = []
            for w in word_s:
                if Multiple.endswith_(w, ['s', 'ss', 'sh', 'ch', 'x' 'z']):
                    pl_word_s.append(f'{w}es')
                elif Multiple.endswith_(w, ['f', 'fe']):
                    if w.endswith('f'):
                        pl_word_s.append(f'{w[:-2]}ves')
                    else:
                        pl_word_s.append(f'{w[:-3]}ves')
                elif Multiple.endswith_(w, ['y']):
                    if w[-2] in 'aeiou':
                        pl_word_s.append(f'{w[:-2]}ies')
                    else:
                        pl_word_s.append(f'{w}s')
                elif Multiple.endswith_(w, ['o']):
                    pl_word_s.append(f'{w}es')
                elif Multiple.endswith_(w, ['us']):
                    pl_word_s.append(f'{w[:-3]}i')
                elif Multiple.endswith_(w, ['os']):
                    pl_word_s.append(f'{w[:-3]}i')
                elif Multiple.endswith_(w, ['is']):
                    pl_word_s.append(f'{w[:-3]}es')
                else:
                    pl_word_s.append(f'{w}s')
            return pl_word_s

        if isinstance(word_s, list):
            return mk_plural(word_s)
        else:
            return mk_plural([word_s])
