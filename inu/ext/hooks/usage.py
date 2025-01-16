import hikari
import lightbulb

from core import logging, getLogger
from utils import InvokationStats

log = getLogger(__name__)

loader = lightbulb.Loader()

@lightbulb.hook(lightbulb.ExecutionSteps.POST_INVOKE)
async def record_command_metrics(_: lightbulb.ExecutionPipeline, ctx: lightbulb.Context) -> None:
    """Hook to log the command usage"""
    try:
        cmd_name = ctx.command_data.qualified_name
        log.info(f"{cmd_name} invoked by {ctx.user.display_name}")
        await InvokationStats.add_or_sub(cmd_name, ctx.guild_id, 1)
    except Exception:
        log.error("Failed to defer command response", exc_info=True)
        return