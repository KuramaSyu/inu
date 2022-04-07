import asyncio
import logging
import typing
from datetime import datetime
from typing import *

import aiohttp
import hikari
import lightbulb
import lightbulb.utils as lightbulb_utils
from core import BotResponseError, Inu, Table, getLogger
from fuzzywuzzy import fuzz
from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds, ResponseType, TextInputStyle
from hikari.events import InteractionCreateEvent
from hikari.impl.special_endpoints import ActionRowBuilder, LinkButtonBuilder
from hikari.messages import ButtonStyle
from jikanpy import AioJikan
from lightbulb import OptionModifier as OM
from lightbulb import commands, context
from lightbulb.context import Context
from matplotlib.style import available
from numpy import full, isin
from typing_extensions import Self
from utils import Colors, Human, Paginator, Reddit, Urban, crumble

log = getLogger(__name__)

class RestDelay:
    def __init__(
        self,
        name: str,
        uri: str = None,
    ):
        self.uri = uri
        self.headers: Optional[Dict[str, str]] = {}
        self.params: Optional[Dict[str, str]] = {}
        self.delay: Optional[float] = -1
        self.status: Optional[int] = 400
        self.coro: Optional[Coroutine] = None
        self.coro_args = None
        self.coro_kwargs = None
        self.name = name
    
    def with_headers(self, **headers) -> Self:
        self.headers = headers
        return self

    def with_params(self, **params) -> Self:
        self.params = params
        return self

    def with_coro(self, coro: Coroutine, args: List[Any] = None, kwargs: Dict[str, Any] = None) -> Self:
        self.coro = coro
        self.coro_args = args or []
        self.coro_kwargs = kwargs or {}
        return self

    async def do_request(self) -> Self:
        if self.coro:
            start = datetime.now()
            await self.coro(*self.coro_args, **self.coro_kwargs)
            self.delay = (datetime.now() - start).microseconds / 1000
            self.status = 200
        else:
            async with aiohttp.ClientSession() as session:
                start = datetime.now()
                async with session.get(self.url, params=self.params, headers=self.headers) as resp:
                    self.delay = (datetime.now() - start).seconds * 1000
                    self.status = resp.status
                await session.close()
        return self

    def __str__(self) -> str:
        if self.delay != -1:
            return f"{self.color} {self.name} {self.delay:.2f} ms"
        else:
            return f"{self.color} {self.name}"

    @property
    def color(self) -> str:
        if self.delay == -1:
            return "⚫"
        elif str(self.status)[0] != "2":
            return "⚫"
        if self.delay >= 800:
            return "🔴"
        elif self.delay >= 500:
            return "🟠"
        elif self.delay >= 200:
            return "🟡"
        else:
            return "🟢"

basics = lightbulb.Plugin("Basics", "Extends the commands with basic commands", include_datastore=True)
if not isinstance(basics.d, lightbulb_utils.DataStore):
    raise RuntimeError("Plugin don't contain a datastore")
if basics.d is None:
    raise RuntimeError("Plugin don't contain a datastore")

bot: Inu


@basics.command
@lightbulb.command("ping", "is the bot alive?")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def ping(ctx: context.Context):
    def ping_to_color(ping: float) -> str:
        if ping >= 500:
            return "🔴"
        elif ping >= 340:
            return "🟠"
        elif ping >= 150:
            return "🟡"
        else:
            return "🟢"

    def ping_to_color_rest(ping: float) -> str:
        if ping >= 1150:
            return "🔴"
        elif ping >= 800:
            return "🟠"
        elif ping >= 450:
            return "🟡"
        else:
            return "🟢"

    def ping_to_color_db(ping: float) -> str:
        if ping >= 80:
            return "🔴"
        elif ping >= 40:
            return "🟠"
        elif ping >= 15:
            return "🟡"
        else:
            return "🟢"

    db_request_start = datetime.now()
    table = Table("bot")
    record = await table.select_row(["key"], ["restart_count"])
    db_delay = datetime.now() - db_request_start
    request_start = datetime.now()
    embed = Embed(
            title="Pong",
            description=(
                f"Bot is alive\n\n"
                f"{ping_to_color(ctx.bot.heartbeat_latency*1000)} Gateway: {ctx.bot.heartbeat_latency*1000:.2f} ms\n\n"
                f"⚫ REST: .... ms\n\n"
                f"{ping_to_color_db(db_delay.total_seconds()*1000)} Database: {db_delay.total_seconds()*1000:.2f} ms"
            ),
    )
    msg = await ctx.respond(embed=embed)
    rest_delay = datetime.now() - request_start
    apis = [
        RestDelay("Reddit API").with_coro(Reddit.get_posts, ["memes"], {"minimum":3, "top":True}),
        # RestDelay("My Anime List API (unofficial)").with_coro(AioJikan().anime, [1]), # unclosed client session
        RestDelay("Urban Dictionary API").with_coro(Urban.fetch, ["stfu"])
    ]
    tasks = [asyncio.create_task(api.do_request()) for api in apis]
    await asyncio.wait(tasks, timeout=5, return_when=asyncio.ALL_COMPLETED)

    embed.description = (
        f"Bot is alive\n\n"
        f"{ping_to_color(ctx.bot.heartbeat_latency*1000)} Gateway: {ctx.bot.heartbeat_latency*1000:.2f} ms\n\n"
        f"{ping_to_color_rest(rest_delay.total_seconds()*1000)} REST: {rest_delay.total_seconds()*1000:.2f} ms\n\n"
        f"{ping_to_color_db(db_delay.total_seconds()*1000)} Database: {db_delay.total_seconds()*1000:.2f} ms\n\n"
    )
    embed.description += "\n\n".join(str(api) for api in apis)
    await msg.edit(embed=embed)

    
@basics.command
@lightbulb.add_cooldown(60*60*10, 15, lightbulb.UserBucket)
@lightbulb.add_checks(
    lightbulb.guild_only, 
    # lightbulb.has_channel_permissions(hikari.Permissions.MANAGE_CHANNELS)
    lightbulb.has_role_permissions(hikari.Permissions.MANAGE_CHANNELS)
)
@lightbulb.option(
    "message_link",
    "Delete until this message",
    default=None,
    type=str,
)
@lightbulb.option(
    "ammount", 
    "The ammount of messages you want to delete, Default: 5", 
    default=None, 
    type=int, 
)
@lightbulb.command("purge", "Delete the last messages from a channel", aliases=["clean"])
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def purge(ctx: context.Context):
    if not (channel := ctx.get_channel()):
        return
    if not isinstance(channel, hikari.TextableGuildChannel):
        return
    if not ctx.options.ammount and not ctx.options.message_link:
        raise BotResponseError(
            f"I need the ammount of messages I should delete, or the message link until which I should delete messages"
        )
    if (ammount := ctx.options.ammount) and ammount > 50:
        raise BotResponseError("I can't delete that much messages")
    if ctx.options.message_link:
        ammount = 50
    messages = []
    ammount += 2
    await ctx.respond("I'll do it. Let me some time. I'll include your message and this message")
    async for m in channel.fetch_history():
        messages.append(m)
        ammount -= 1
        if ammount <= 0:
            break
        elif ctx.options.message_link and m.make_link(ctx.guild_id) == ctx.options.message_link.strip():
            break
    if ctx.options.message_link and ammount <= 0:
        raise BotResponseError(f"Your linked message is not under the last 50 messages")
    await channel.delete_messages(messages)

@basics.command
@lightbulb.command("invite", "Invite this bot to your server")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def invite(ctx: context.Context):
    await ctx.respond(
        embed=Embed(
            title="Invite me",
            description=f"[Click here]({ctx.bot.conf.bot.DISCORD_INVITE_LINK}) _or click the button_",
            color=Colors.from_name("mediumslateblue"),
        ).set_thumbnail(ctx.bot.get_me().avatar_url),
        component=(
            ActionRowBuilder()
            .add_button(
                ButtonStyle.LINK, 
                ctx.bot.conf.bot.DISCORD_INVITE_LINK
            ).set_label("my invite link").add_to_container()
        )
    )

@basics.command
@lightbulb.command("search", "search different things and get it's ID with the name")
@lightbulb.implements(commands.SlashCommandGroup, commands.PrefixCommandGroup)
async def search(ctx: Context):
    pass

@search.child
@lightbulb.option(
    "guild", 
    "The name/part of the name/id from the guild", 
    modifier=OM.CONSUME_REST,
    type=str,
)
@lightbulb.command(
    "guild", 
    "seach guilds/servers and get it's ID with the name",
    aliases=["server"]
)
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def search_guild(ctx: Context):
    matches = await bot.search.guild(ctx.options.guild)
    if not matches:
        await ctx.respond(f"No guilds with partial ID/name `{ctx.options.guild}` found")
        return
    str_matches = "\n".join(f"name: {g.name:<35} id: {str(g.id):>}" for g in matches)
    result = (
        f"I found {Human.plural_('guild', len(matches), with_number=True)}:\n"
        f"```\n{str_matches}\n```"
    )
    pag = Paginator(page_s=[f"```\n{p.replace('```', '')}```" for p in crumble(result)])
    await pag.start(ctx)

@search.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option(
    "member", 
    "A part of the name/id/alias of the member from the guild", 
    modifier=OM.CONSUME_REST,
    type=str,
)
@lightbulb.command(
    "member", 
    "seach a member in this guild",
    aliases=["user", "person"]
)
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def search_member(ctx: Context):
    matches = await bot.search.member(ctx.guild_id, ctx.options.member)
    if not matches:
        await ctx.respond(f"No member with partial name/ID/alias `{ctx.options.member}` found")
        return
    str_matches = "\n".join(f"name: {m.display_name:<35} id: {str(m.id):>}" for m in matches)
    result = (
        f"I found {Human.plural_('member', len(matches), with_number=True)}:\n"
        f"```\n{str_matches}\n```"
    )
    pag = Paginator(page_s=[f"```\n{p.replace('```', '')}```" for p in crumble(result)])
    await pag.start(ctx)

# @basics.command
# @lightbulb.command("testmodal", "Ping the bot", hidden=True)
# @lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
# async def testmodal(ctx: context.Context):
#     modal = (
#         ActionRowBuilder()
#         .add_text_input("test_modal", "The title")
#         .set_placeholder("test placeholder")
#         .add_to_container()
#     )

#     resp = await ctx.interaction.create_modal_response("title from interac", "custom_id", components=[modal])
#     cast(Inu, ctx.bot)
#     bot: Inu = ctx.bot
#     d, i, _ = await bot.wait_for_.modal(
#         "custom_id",
#     )
#     await i.create_initial_response(ResponseType.MESSAGE_CREATE, f"{d}")

@basics.command
@lightbulb.command("testmodal", "test command for modal interactions", hidden=True)
@lightbulb.implements(commands.SlashCommand)
async def testmodal(ctx: context.Context):
    bot: Inu = ctx.bot
    answers, interaction, _ = await bot.shortcuts.ask_with_modal(
        "Tag", 
        ["Name:", "Value:"], 
        interaction=ctx.interaction,
        input_style_s=[TextInputStyle.SHORT, TextInputStyle.PARAGRAPH],
        placeholder_s=[None, "What you will see, when you do /tag get <name>"],
        is_required_s=[True, None],
        pre_value_s=[None, "Well idc"]

    )
    await interaction.create_initial_response(ResponseType.MESSAGE_CREATE, f"{answers}")




def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(basics)

