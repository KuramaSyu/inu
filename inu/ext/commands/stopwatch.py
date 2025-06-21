import asyncio
from typing import *
from datetime import datetime, timedelta
import hikari
import lightbulb
import json

from fuzzywuzzy import fuzz
from hikari import (
    ComponentInteractionCreateEvent,
    Embed,
    ResponseType, 
    TextInputStyle,
    ButtonStyle,
    InteractionCreateEvent,
    Permissions,
    ApplicationContextType
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import commands, context, SlashCommand, invoke
from lightbulb.prefab import sliding_window
from humanize import precisedelta

from utils import (
    Colors, 
    Human, 
    Paginator, 
    crumble
)
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger,
    InuContext,
    get_context
)

log = getLogger(__name__)

plugin = lightbulb.Loader()
bot: Inu


def get_stopwatch_custom_id(action: str, elapsed_time: float, is_running: bool, start_time: datetime) -> str:
    return json.dumps({
        "t": "stw",  # type stopwatch
        "a": action,  # action
        "e": round(elapsed_time, 1),  # elapsed time in seconds
        "ts": round(start_time.timestamp(), 1),  # start time
        "r": is_running,  # is running
    }, separators=(",", ":"), indent=None)


def extract_stopwatch_custom_id(custom_id: str | dict) -> Tuple[str, float, float, bool]:
    """
    Returns:
    --------
    action: str
    elapsed_time: float
    start_time: float
    is_running: bool
    """
    d = json.loads(custom_id) if isinstance(custom_id, str) else custom_id
    return d["a"], d["e"], d["ts"], d["r"]


def get_stopwatch_message_content(elapsed_time: float, is_running: bool, started: datetime) -> str:
    msg = f"Elapsed time: **{precisedelta(timedelta(seconds=elapsed_time))}**"
    if is_running:
        msg += f"\n\nstarted <t:{int(started.timestamp())}:R>"
    return msg


def get_stopwatch_message_components(custom_id_json: dict) -> List[MessageActionRowBuilder]:
    action, elapsed_time, start_time, is_running = extract_stopwatch_custom_id(custom_id_json)
    start_stop_button = ButtonStyle.PRIMARY if is_running else ButtonStyle.SUCCESS
    start_stop_label = "Pause" if is_running else "Start"
    start_stop_emoji = "⏸" if is_running else "▶️"
    start_or_stop = "stop" if is_running else "start"
    args = (elapsed_time, is_running, datetime.fromtimestamp(start_time))

    action_row = (
        MessageActionRowBuilder()
        .add_interactive_button(
            start_stop_button,
            get_stopwatch_custom_id(start_or_stop, *args),
            emoji=start_stop_emoji
        )
    )
    if not is_running:
        action_row = (
            action_row
            .add_interactive_button(
                ButtonStyle.SECONDARY,
                get_stopwatch_custom_id("reset", *args),
                emoji="🔄"
            )
            .add_interactive_button(
                ButtonStyle.SECONDARY,
                get_stopwatch_custom_id("delete", *args),
                emoji="❌"
            )
        )
    return [action_row]
    


async def handle_stopwatch_action(ctx: InuContext, custom_id: dict):
    elapsed_time = custom_id.get("e", 0)
    is_running: bool = custom_id.get("r", False)
    start_time: datetime = datetime.fromtimestamp(custom_id.get("ts", datetime.now().timestamp()))

    if custom_id["a"] == "stop":
        elapsed_time += (
            datetime.now() - datetime.fromtimestamp(custom_id["ts"])
        ).total_seconds()
        is_running = False
    elif custom_id["a"] == "start":
        start_time = datetime.now()
        is_running = True
    elif custom_id["a"] == "reset":
        elapsed_time = 0
    elif custom_id["a"] == "delete":
        await ctx.respond(
            get_stopwatch_message_content(elapsed_time, is_running, start_time),
            update=True,
            components=[]
        )
        await ctx.delete_initial_response()
        return
    custom_id["e"] = elapsed_time
    custom_id["r"] = is_running
    custom_id["ts"] = start_time.timestamp()
    custom_id["a"] = "stop" if is_running else "start"

    await ctx.respond(
        get_stopwatch_message_content(elapsed_time, is_running, start_time),
        update=True,
        components=get_stopwatch_message_components(custom_id)
    )


@plugin.listener(ComponentInteractionCreateEvent)
async def on_interaction_create(event: InteractionCreateEvent):
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    d = None
    try:
        d = json.loads(event.interaction.custom_id)
        if d["t"] != "stw":
            # not a stopwatch
            return
        action = d["a"]
        if action not in ("start", "stop", "reset", "delete"):
            # not a valid action for stopwatch
            return
        # just check the keys
        elaped_time = d["e"]
        is_running = d["r"]
    except json.JSONDecodeError:
        return
    except KeyError:
        return
    ctx = get_context(event)
    await handle_stopwatch_action(ctx, d)


@plugin.command
class StopwatchCommand(
    SlashCommand,
    name="stopwatch",
    description="A stopwatch",
    contexts=[ApplicationContextType.GUILD],
    default_member_permissions=None,
    hooks=[sliding_window(3, 1, "user")]
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await ctx.respond(
            get_stopwatch_message_content(0, False, datetime.now()),
            components=get_stopwatch_message_components({
                "a": "start",
                "e": 0,
                "ts": round(datetime.now().timestamp(), 1),
                "r": False,
            })
        )


