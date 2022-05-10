
from .colors import Colors
from .string_crumbler import crumble, StringCutter, WordIterator
from .language import Human, Multiple
from .string_calculator import NumericStringParser, calc

from .grid import Grid
from .vote import *
from .rest import *
from .db import *
from .logger import *

from .emojis import Emoji

from .paginators import *



import logging
from core._logging import LoggingHandler
logging.setLoggerClass(LoggingHandler)