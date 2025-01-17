import asyncio
from typing import *
from datetime import datetime
import hikari
import lightbulb

from fuzzywuzzy import fuzz
from hikari import (
    Embed,
    ResponseType, 
    TextInputStyle,
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import commands, context, SlashCommand, invoke


from utils import (
    Colors, 
    Human, 
    Paginator, 
    crumble,
    xkcdAPI,
    xkcdComicDict,
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

loader = lightbulb.Loader()
bot: Inu

@loader.listener(hikari.InteractionCreateEvent)
async def on_interaction(event: hikari.InteractionCreateEvent):
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return

    # check if ckcd event
    striped_custom_id = ""
    if event.interaction.custom_id.startswith("xkcd_"):
        striped_custom_id = event.interaction.custom_id.replace("xkcd_", "")
    
    if not striped_custom_id:
        return
    ctx = get_context(event)
    await ctx.defer(update=True if not "copy" in striped_custom_id else False)
    try:
        if striped_custom_id == "random":
            comic = await xkcdAPI.fetch_comic(
                comic_url=xkcdAPI.random_comic_endpoint()
            )
            await send_comic(ctx, comic)
        elif striped_custom_id.startswith("hashtag_"):
            hashtag = int(striped_custom_id.replace("hashtag_", ""))
            comic = await xkcdAPI.fetch_comic(
                comic_url=xkcdAPI.specific_comic_endpoint(hashtag)
            )
            await send_comic(ctx, comic)
        elif striped_custom_id.startswith("stop_"):
            hashtag = int(striped_custom_id.replace("stop_", ""))
            comic = await xkcdAPI.fetch_comic(
                comic_url=xkcdAPI.specific_comic_endpoint(hashtag)
            )
            await send_comic(
                ctx, 
                comic, 
                add_random_button=False, 
                add_navigation_buttons=False
            )
        elif striped_custom_id.startswith("copy_"):
            hashtag = int(striped_custom_id.replace("copy_", ""))
            comic = await xkcdAPI.fetch_comic(
                comic_url=xkcdAPI.specific_comic_endpoint(hashtag)
            )
            await send_comic(
                ctx, 
                comic, 
                add_random_button=True, 
                add_navigation_buttons=True
            )
    except BotResponseError as e:
        pass

group = lightbulb.Group(name="xkcd", description="Commands to access the xkcd comics")

@group.register
class Random(
    SlashCommand,
    name="random",
    description="Get a random xkcd comic"
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        comic = await xkcdAPI.fetch_comic(
            comic_url=xkcdAPI.random_comic_endpoint()
        )
        await send_comic(ctx, comic, True)

@group.register
class Current(
    SlashCommand,
    name="current",
    description="Get the current xkcd comic"
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        comic = await xkcdAPI.fetch_comic(
            comic_url=xkcdAPI.current_comic_endpoint()
        )
        await send_comic(ctx, comic)

@group.register
class WithHashtag(
    SlashCommand,
    name="with-hashtag",
    description="Get a specific xkcd comic"
):
    hashtag = lightbulb.integer("hashtag", "The hashtag of the comic you want to get")

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        comic = await xkcdAPI.fetch_comic(
            comic_url=xkcdAPI.specific_comic_endpoint(self.hashtag)
        )
        await send_comic(ctx, comic)

loader.command(group)

async def send_comic(
        ctx: InuContext, 
        comic: xkcdComicDict | None,
        add_random_button: bool = True,
        add_navigation_buttons: bool = True,
    ):
    """
    Creates and sends embed of an xkcdComicDict
    """
    if not comic:
        raise BotResponseError("Seems like your comic does not exist")
    embed = Embed(
        title=(
            f"{comic['title']}"
        ),
        description=(
            f"{comic['alt']}"
        ),
        color=Colors.random_color()
    )
    embed.add_field("Link", f"[Click Here]({comic['link']})", inline=True)
    embed.add_field("Explanation", f"[Click Here]({comic['explanation_url']})", inline=True)
    embed.add_field("Date", f"{comic['year']}-{comic['month']}-{comic['day']}", inline=True)
    embed.set_image(comic["img"])
    embed.set_footer(text=f"XKCD #{comic['num']}")
    components = []
    row = MessageActionRowBuilder()
    # previous button
    if add_navigation_buttons:
        row.add_interactive_button(
            hikari.ButtonStyle.PRIMARY, 
            f"xkcd_hashtag_{comic['num'] - 1}",
            emoji="◀️"
        )
    # random button
    if add_random_button:
        row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY, 
            "xkcd_random",
            emoji="🎲"
        )
    # add button for removing components
    if add_random_button or add_navigation_buttons:
        row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY, 
            f"xkcd_stop_{comic['num']}",
            emoji="⏹️"
        )
        row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY, 
            f"xkcd_copy_{comic['num']}",
            emoji="⤵️",
            label="Clone"
        )
    # next button
    if add_navigation_buttons:
        row.add_interactive_button(
            hikari.ButtonStyle.PRIMARY, 
            f"xkcd_hashtag_{comic['num'] + 1}",
            emoji="▶️"
        )
    if add_navigation_buttons or add_random_button:
        components.append(row)
    await ctx.respond(
        embed=embed,
        components=components
    )

