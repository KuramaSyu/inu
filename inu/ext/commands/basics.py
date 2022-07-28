import asyncio
import logging
import typing
from datetime import datetime
from typing import *
import traceback

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
from utils import Colors, Human, Paginator, Reddit, Urban, crumble, MyAnimeList, BoredAPI, IP

log = getLogger(__name__)
bot: Inu = None



class RestDelay:
    """Class to test delays of REST APIs via passing methods or urls into the builder"""
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
        self.coro: Optional[Callable[[Any], Awaitable]] = None
        self.coro_args = None
        self.coro_kwargs = None
        self.name = name
    
    def with_headers(self, **headers) -> "RestDelay":
        self.headers = headers
        return self

    def with_params(self, **params) -> "RestDelay":
        self.params = params
        return self

    def with_coro(self, coro: Callable[[Any], Awaitable], args: Optional[List[Any]] = None, kwargs: Optional[Dict[str, Any]] = None) -> "RestDelay":
        self.coro = coro
        self.coro_args = args or []  # type: ignore
        self.coro_kwargs = kwargs or {}  # type: ignore
        return self

    async def do_request(self) -> "RestDelay":
        try:
            if self.coro:
                start = datetime.now()
                await self.coro(*self.coro_args, **self.coro_kwargs)
                self.delay = (datetime.now() - start).total_seconds() * 1000
                self.status = 200
            else:
                async with aiohttp.ClientSession() as session:
                    start = datetime.now()
                    async with session.get(self.url, params=self.params, headers=self.headers) as resp:
                        self.delay = (datetime.now() - start).seconds * 1000
                        self.status = resp.status
                    await session.close()
        except Exception:
            self.delay = -1
            self.status = 400
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



@basics.command
@lightbulb.command("ping", "is the bot alive?")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def ping(ctx: context.Context):
    request_start = datetime.now()
    embed = Embed(
            title="Pong",
            description=(
                f"Bot is alive\n\n"
                f"{ping_to_color(ctx.bot.heartbeat_latency*1000)} Gateway: {ctx.bot.heartbeat_latency*1000:.2f} ms\n\n"
                f"⚫ REST: .... ms\n\n"
            ),
    )
    msg = await ctx.respond(embed=embed)
    rest_delay = datetime.now() - request_start
    embed.description = (
        f"Bot is alive\n\n"
        f"{ping_to_color(ctx.bot.heartbeat_latency*1000)} Gateway: {ctx.bot.heartbeat_latency*1000:.2f} ms\n\n"
        f"{ping_to_color_rest(rest_delay.total_seconds()*1000)} REST: {rest_delay.total_seconds()*1000:.2f} ms\n\n"
    )
    embed.add_field("Public IP", await IP.fetch_public_ip(), inline=True)
    embed.add_field("Domain:", "inuthebot.ddns.net\n\n(can be used instead of the IP Adress)", inline=True)
    await msg.edit(embed=embed)



@basics.command 
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.command("status", "get information to the current status of the bot")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def status(ctx: context.Context):
    request_start = datetime.now()
    embed = Embed(
            title="Status",
            description=(
                f"{ping_to_color(ctx.bot.heartbeat_latency*1000)} Gateway: {ctx.bot.heartbeat_latency*1000:.2f} ms\n\n"
                f"⚫ REST: .... ms\n\n"
            ),
    )
    msg = await ctx.respond(embed=embed)
    rest_delay = datetime.now() - request_start

    apis = [
        RestDelay("Database").with_coro(Table("bot").select_row, [["key"], ["restart_count"]]),
        RestDelay("Reddit API").with_coro(Reddit.get_posts, ["memes"], {"minimum":3, "top":True}),
        RestDelay("Urban Dictionary API").with_coro(Urban.fetch, ["stfu"]),
        RestDelay("MyAnimeList API").with_coro(MyAnimeList.search_anime, ["naruto"]),
        RestDelay("Bored API").with_coro(BoredAPI.fetch_idea),
    ]
    tasks = [asyncio.create_task(api.do_request()) for api in apis]
    await asyncio.wait(tasks, timeout=8, return_when=asyncio.ALL_COMPLETED)

    embed.description = (
        f"{ping_to_color(ctx.bot.heartbeat_latency*1000)} Gateway: {ctx.bot.heartbeat_latency*1000:.2f} ms\n\n"
        f"{ping_to_color_rest(rest_delay.total_seconds()*1000)} REST: {rest_delay.total_seconds()*1000:.2f} ms\n\n"
    )
    embed.description += "\n\n".join(str(api) for api in apis)
    embed.add_field(
        "IPs",
        (        
            "```"
            f"{'Public IP:':<15}{await IP.fetch_public_ip()}\n"
            f"{'Private IP:':<15}{IP.get_private_ip()}\n"
            "```"
        )
    )
    await msg.edit(embed=embed)



@basics.command
@lightbulb.add_cooldown(3, 1, lightbulb.UserBucket)
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
@lightbulb.command("info", "Get information about the user")
@lightbulb.implements(commands.UserCommand)
async def user_info(ctx: context.UserContext):
    bot: Inu = ctx.bot
    author: hikari.Member = ctx.options.target
    embed = hikari.Embed(title=f"About {author.display_name}", color=Colors.default_color())
    embed.add_field(name="Full name", value=str(author), inline=True)
    embed.add_field(name="ID", value=f"`{author.id}`")
    embed.add_field(name="Created at", value=f"<t:{author.created_at.timestamp():.0f}:F>", inline=True)
    embed.add_field(name="Flags", value=f"{author.flags}", inline=True)
    embed.add_field(name="Joined here", value=f"<t:{author.joined_at.timestamp():.0f}:F>", inline=True)
    embed.add_field(name="Roles", value=f"{', '.join([r.mention for r in await bot.mrest.fetch_roles(author)])}", inline=True)
    embed.add_field(
        name=f"About {author.get_guild().name}", 
        value=(
            f"**ID**: `{author.get_guild().id}`\n"
            f"**Owner**: {(await ctx.bot.mrest.fetch_member(author.guild_id, author.get_guild().owner_id)).display_name}\n"
            f"**Created at**: <t:{author.get_guild().created_at.timestamp():.0f}:F>\n"
            f"**Members**: {len(author.get_guild().get_members())}\n"
            f"**Channels**: {len(author.get_guild().get_channels())}\n"
            f"**Roles**: {len(author.get_guild().get_roles())}\n"
            f"**Emojis**: {len(author.get_guild().get_emojis())}\n"
        ),
        inline=True
    )
    embed.set_thumbnail(author.avatar_url)

    await ctx.respond(embed=embed)


@basics.command
@lightbulb.add_cooldown(3, 1, lightbulb.UserBucket)
@lightbulb.add_checks(
    lightbulb.guild_only, 
    # lightbulb.has_channel_permissions(hikari.Permissions.MANAGE_CHANNELS)
    lightbulb.has_role_permissions(hikari.Permissions.MANAGE_CHANNELS)
)
@lightbulb.command("purge until here", "Delete all messages until the message (including)")
@lightbulb.implements(commands.MessageCommand)
async def purge_until_this_message(ctx: context.MessageContext):
    await ctx.respond(f"Let me get the trash bin ready...\nY'know, this thing is pretty heavy")
    try:
        bot: Inu = ctx.bot
        message_id: int = ctx.options.target.id
        messages = []
        amount = 50
        async for m in ctx.get_channel().fetch_history():
            messages.append(m)
            amount -= 1
            if amount <= 0:
                break
            elif m.id == message_id:
                break
        if amount <= 0:
            raise BotResponseError(f"Your linked message is not under the last 50 messages")
        await ctx.get_channel().delete_messages(messages)
    except:
        log.error(traceback.format_exc())



@basics.command
@lightbulb.command("add alias / nickname / name", "Get information about the user")
@lightbulb.implements(commands.UserCommand)
async def add_alias(ctx: context.UserContext):
    member: hikari.Member = await bot.mrest.fetch_member(
        guild_id=ctx.guild_id,
        member_id=ctx.options.target.id,
    )
    answers, interaction, event = await bot.shortcuts.ask_with_modal(
        modal_title="Add alias",
        question_s=["Nickname:", "Alias / Name:", "Seperater between name and alias:"],
        pre_value_s=[member.display_name.split("|")[0], "", "|"],
        input_style_s=[TextInputStyle.SHORT, TextInputStyle.SHORT, TextInputStyle.SHORT],
        interaction=ctx.interaction,
    )
    nickname, alias, seperator = answers
    ctx._interaction = interaction
    try:
        await member.edit(nickname=f"{nickname} {seperator} {alias}")
    except hikari.ForbiddenError as e:
        await ctx.respond(
            f"I don't have the permissions to edit nicknames. Some permissions are missing.",
            flags=hikari.MessageFlag.EPHEMERAL,
        )       
        raise e
    await ctx.respond(
        f"Added alias `{alias}` to {member.display_name}\nNew name: {nickname} {seperator} {alias}",
        flags=hikari.MessageFlag.EPHEMERAL,
    )




    


def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(basics)

