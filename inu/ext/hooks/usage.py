import hikari
import lightbulb

from core import logging, getLogger
from utils import InvokationStats

LOG_USAGE = lightbulb.ExecutionStep("LOG_USAGE")
log = getLogger(__name__)

loader = lightbulb.Loader()

