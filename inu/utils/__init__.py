
from .models import Singleton
from .string_crumbler import crumble
from .colors import Color, Colors
from .logging import LoggingHandler
from .paginators import Paginator
import logging
logging.setLoggerClass(LoggingHandler)