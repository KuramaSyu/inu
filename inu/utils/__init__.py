
from .models import Singleton
from .paginators.common import Paginator
from .string_crumbler import crumble
from .colors import Color, Colors
from .logging import LoggingHandler
import logging
logging.setLoggerClass(LoggingHandler)