import asyncio
from typing import *
from datetime import datetime
import hikari
import lightbulb
import json

from fuzzywuzzy import fuzz
from hikari import (
    Embed,
    ResponseType, 
    TextInputStyle,
    ButtonStyle,
    InteractionCreateEvent
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import commands, context


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

plugin = lightbulb.Plugin("Name", "Description")
bot: Inu

def get_counter_custom_id(action: str, counter: int, title: str, all_visible: bool = True) -> str:
    return json.dumps({
        "a": action,  # action
        "c": counter,  # counter
        "t": title,  # title
        "v": all_visible,
    }, separators=(",", ":"), indent=None)

def get_counter_message_content(counter: int, title: str) -> str:
    msg = f"Counter: **{counter}**"
    if title:
        msg = f"**{title}**\n\n{msg}"
    return msg

def get_counter_message_components(counter: int, title: str, all_visible: bool) -> List[MessageActionRowBuilder]:
    args = [counter, title, all_visible]
    rows = []

    if all_visible:
        # add option buttons if needed
        rows.append(
        MessageActionRowBuilder()
            .add_button(ButtonStyle.SECONDARY, get_counter_custom_id("reset", *args))
                .set_label("Reset").set_emoji("🔄").add_to_container()
            .add_button(ButtonStyle.SECONDARY, get_counter_custom_id("resend", *args)) # bottom arrow emoji: ⬇️
                .set_label("to bottom").set_emoji("⬇️").add_to_container()
            .add_button(ButtonStyle.SECONDARY, get_counter_custom_id("delete", *args))
                .set_label("Close").set_emoji("❌").add_to_container()
        ),

    # add increment button
    rows.append(
        MessageActionRowBuilder()
            .add_button(ButtonStyle.PRIMARY, get_counter_custom_id("incr", *args))
                .set_label("+1").add_to_container()
        )
    if all_visible:
        # add decrement button if needed
        (
            rows[-1]
            .add_button(ButtonStyle.PRIMARY, get_counter_custom_id("decr", *args))
                .set_label("-1").add_to_container()
            .add_button(ButtonStyle.PRIMARY, get_counter_custom_id("hide", *args))# 
                .set_label("<").add_to_container() 
        )
    else:
        # add show button otherwise
        (
            rows[-1]
            .add_button(ButtonStyle.SECONDARY, get_counter_custom_id("show", *args))
                .set_label(">").add_to_container()
        )
    return rows



@plugin.listener(hikari.InteractionCreateEvent)
async def on_coutner_button(event: InteractionCreateEvent):
    """
    A message with the counter as content.
    components has following custom_id structure:
    {
        "action": "",
        "counter": 0,
        "title": "",
    }
    the message should have following buttons:
        - increment
        - decrement
        - reset
        - resend message
        - delete message
    """
    custom_id = None
    try:
        # un json the custom_id
        custom_id = json.loads(event.interaction.custom_id)
    except (json.JSONDecodeError, AttributeError):
        return
    # check if the custom_id is valid
    if not isinstance(custom_id, dict):
        return
    if not (action := custom_id.get("a")):
        return
    if (counter := custom_id.get("c")) is None:
        return
    if (all_visible := custom_id.get("v")) is None:
        return
    
    title: str = custom_id.get("t", "")
    
    

    ctx = get_context(event)
    if action == "incr":
        counter += 1
    elif action == "decr":
        counter -= 1
    elif action == "reset":
        counter = 0
    elif action == "hide":
        all_visible = False
    elif action == "show":
        all_visible = True

    args = [counter, title, all_visible]
    
    if action == "resend":
        await ctx.respond(
            get_counter_message_content(*args[:2]), 
            update=True, 
            components=get_counter_message_components(*args)
        )
        await ctx.delete_initial_response()
        await ctx.respond(
            get_counter_message_content(*args[:2]), 
            components=get_counter_message_components(*args)
        )
        return
    elif action == "delete":
        await ctx.respond(
            get_counter_message_content(*args[:2]), 
            update=True, 
            components=get_counter_message_components(*args)
        )
        await ctx.delete_initial_response()
        return
    
    await ctx.respond(
        get_counter_message_content(*args[:2]), 
        components=get_counter_message_components(*args),
        update=True
    )

@plugin.command
@lightbulb.option("title", "The title of the counter", type=str, default="")
@lightbulb.option("start-at", "The counter to start with", type=int, default=0)
@lightbulb.command("counter", "A counter")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def counter(ctx: context.Context):
    title: str = ctx.options["title"]
    start_at: int = ctx.options["start-at"]
    ctx = get_context(ctx.event)
    MAX_TITLE_LENGTH = 60
    if len(title) > MAX_TITLE_LENGTH:
        await ctx.respond(f"The title is {Human.plural_('character', len(title) - MAX_TITLE_LENGTH)} to long", ephemeral=True)
        return
    await ctx.respond(
        get_counter_message_content(start_at, title), 
        components=get_counter_message_components(start_at, title, False)
    )




def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

