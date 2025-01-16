import hikari
import lightbulb

from core import logging, getLogger
from utils import InvokationStats

LOG_USAGE = lightbulb.ExecutionStep("LOG_USAGE")
log = getLogger(__name__)


# Define our hook to defer the command response
@lightbulb.hook(LOG_USAGE)
async def auto_defer_command_response(_: lightbulb.ExecutionPipeline, ctx: lightbulb.Context) -> None:
    try:
        log.info(f"{ctx.command_data.qualified_name} invoked by {ctx.user.display_name}")
    except Exception:
        log.error("Failed to defer command response", exc_info=True)
        return
    #await InvokationStats.add_or_sub(event.command.qualname, event.context.guild_id, 1)