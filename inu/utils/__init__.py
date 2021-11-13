
from .models import Singleton
from .string_crumbler import crumble
from .colors import Color, Colors
from .logging import LoggingHandler
from .paginators import Paginator
import logging
from .reddit import Reddit
logging.setLoggerClass(LoggingHandler)