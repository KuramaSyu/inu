import asyncio
from datetime import datetime, timedelta
from typing import *
import traceback

import aiohttp
import hikari
from hikari.impl import MessageActionRowBuilder
import lightbulb
import lightbulb.utils as lightbulb_utils
from lightbulb import Context
from lightbulb.prefab import sliding_window

from core import (
    BotResponseError, Inu, Table, 
    getLogger, get_context
)
from hikari import (
    ActionRowComponent, ButtonStyle, ComponentInteraction, 
    Embed, GatewayGuild, InteractionCreateEvent, 
    MessageCreateEvent, embeds, ResponseType, TextInputStyle,
    Permissions
)
from tabulate import tabulate
from lightbulb import (
    commands, SlashCommand, invoke, Context, 
)
from tmdb import route
from utils import (
    Colors, Human, Paginator, GuildPaginator,
    Reddit, Urban, crumble, MyAnimeList, 
    BoredAPI, IP, Facts, xkcdAPI,
)
from utils.shortcuts import display_name_or_id

# conditional
lavalink = None

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
        self.delay: float = -1
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
                resp = await self.coro(*self.coro_args, **self.coro_kwargs)
                self.delay = (datetime.now() - start).total_seconds() * 1000
                self.status = 400 if resp is False else 200
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
            return "🟣"
        if self.delay >= 1500:
            return "🔴"
        elif self.delay >= 1000:
            return "🟠"
        elif self.delay >= 750:
            return "🟡"
        else:
            return "🟢"


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
    if ping >= 1500:
        return "🔴"
    elif ping >= 1000:
        return "🟠"
    elif ping >= 750:
        return "🟡"
    else:
        return "🟢"

loader = lightbulb.Loader()

@loader.listener(InteractionCreateEvent)
async def on_interaction(event: InteractionCreateEvent):
    """Listens for Guild-Paginator interactions"""
    if not isinstance(event.interaction, ComponentInteraction):
        return
    if event.interaction.custom_id == "pag-guilds":
        guilds = [g for g in bot.cache.get_guilds_view().values()]
        pag = GuildPaginator([])
        await pag.start(get_context(event), guilds)


@loader.command
class PingCommand(
    lightbulb.SlashCommand,
    name="ping",
    description="Simple Ping"
):
    @lightbulb.invoke
    async def ping(self, ctx: Context):
        task = asyncio.create_task(
            IP.fetch_public_ip(), 
            name="IP"
        )
        task_2 = asyncio.create_task(
            xkcdAPI.fetch_comic(xkcdAPI.random_comic_endpoint()), 
            name="comic"
        )
        #fact = await Facts.fetch_random_fact()

        embed = Embed(title="Pong")
        embed.description = (
            
            f"{ping_to_color(ctx.client.lat*1000)} Gateway: {ctx.bot.heartbeat_latency*1000:.2f} ms\n\n"
            f"⚫ REST: .... ms\n\n"
        )
        embed.add_field("Public IP", "....", inline=True)
        if bot.conf.bot.domain:
            embed.add_field("Domain:", f"{bot.conf.bot.domain}", inline=True)
        
        request_start = datetime.now()
        msg = await ctx.respond(embed=embed)
        rest_delay = datetime.now() - request_start

        done, pending = await asyncio.wait([task, task_2], timeout=8)
        ip = None
        comic = {}
        for d in done:
            if d.get_name() == "IP":
                ip = d.result()
            if d.get_name() == "comic":
                comic = d.result()
        
        for p in pending:
            p.cancel()

        if (title := comic.get("title")):
            embed.title += f" -- {title}"
        embed.description = (
            f"{ping_to_color(ctx.bot.heartbeat_latency*1000)} Gateway: {ctx.bot.heartbeat_latency*1000:.2f} ms\n\n"
            f"{ping_to_color_rest(rest_delay.total_seconds()*1000)} REST: {rest_delay.total_seconds()*1000:.2f} ms\n\n"
        )
        # reset fields
        embed._fields = []
        embed.add_field("Public IP", ip, inline=True)
        if bot.conf.bot.domain:
            embed.add_field("Domain:", f"{bot.conf.bot.domain}", inline=True)
        if (comic_link := comic.get("img")):
            embed.set_image(comic_link)
        if comic:
            embed.add_field("Comic", (
                f"release date: {comic.get('year')}-{comic.get('month', '??')}-{comic.get('day', '??')}\n"
                f"number: {comic.get('num')}\n"
                f"[link]({comic.get('link')})\n"
                f"[explanation]({comic.get('explanation_url')})"
            ))
        await msg.edit(embed=embed)


async def tmdb_coro(search: str):
    show_route = route.Show()
    show_json = await show_route.search(search)
    await show_route.session.close()

async def lavalink_test_coro() -> bool:
    """
    Whether the lavalink connection to YT is working
    """
    if not bot.conf.lavalink.connect:
        return False
    lavalink = None
    if bot.conf.lavalink.connect:
        from ._music import lavalink
    test_title = "Alan Walker - Faded"
    query_information = await lavalink.auto_search_tracks(test_title)
    if len(query_information.tracks) == 0:
        return False
    return True
        

@loader.command
class Status(
    lightbulb.SlashCommand,
    name="status",
    description="Get the status of the bot",
):
    @invoke
    async def status(self, ctx: Context):
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
            # RestDelay("Facts API").with_coro(Facts._fetch_from_rest),
            RestDelay("TMDB API").with_coro(tmdb_coro, ["game of thrones"]),
            RestDelay("xkcd API").with_coro(xkcdAPI.fetch_comic, [xkcdAPI.random_comic_endpoint()]),
            RestDelay("Lavalink API - YT").with_coro(lavalink_test_coro)
        ]
        tasks = [asyncio.create_task(api.do_request()) for api in apis]
        await asyncio.wait(tasks, timeout=20, return_when=asyncio.ALL_COMPLETED)

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
        embed.add_field(f"Daily DB calls", f"```py\n{bot.db.daily_queries.tail(7)}```", inline=False)
        embed.add_field(f"Hourly DB calls", f"```py\n{bot.db.hourly_queries.tail(24)}```", inline=False)
        embed.add_field(f"Guilds:", f"{len(bot.cache.get_guilds_view())}")
        await msg.edit(embed=embed, 
            components=[ 
                MessageActionRowBuilder()
                .add_interactive_button(ButtonStyle.SECONDARY, "pag-guilds", label="Guilds")
            ]
        )

@loader.command
class Purge(
    SlashCommand,
    name="purge",
    description="Delete the last messages from a channel",
    dm_enabled=False,
    default_member_permissions=Permissions.MANAGE_MESSAGES,
    hooks=[sliding_window(3, 1, "user")]
):
    message_link = lightbulb.string("message-link", "Delete until this message", default=None)
    amount = lightbulb.integer("amount", "The amount of messages you want to delete, Default: 5", default=None)

    @invoke
    async def purge(self, ctx: lightbulb.Context):
        userid_to_amount: Dict[int, int] = {}
        MAX_AMOUNT = 100
        if not (channel := ctx.get_channel()):
            return
        if not isinstance(channel, hikari.TextableGuildChannel):
            return
        if not ctx.options.amount and not ctx.options.message_link:
            raise BotResponseError(
                f"I need the amount of messages I should delete, or the message link until which I should delete messages"
            )
        if (amount := ctx.options.amount) and amount > MAX_AMOUNT:
            raise BotResponseError("I can't delete that much messages")
        if ctx.options.message_link:
            amount = MAX_AMOUNT
        messages = []
        amount += 2
        table = tabulate(userid_to_amount, tablefmt="rounded_outline", headers=["User", "Amount"])
        delete_in = datetime.now() + timedelta(seconds=20)
        answer = await ctx.respond(
            f"I'll do it. Let me some time.\n<t:{delete_in.timestamp():.0f}:R>",
            delete_after=20
        )
        async for m in channel.fetch_history():
            if m.author.id not in userid_to_amount:
                userid_to_amount[m.author.id] = 0
            userid_to_amount[m.author.id] += 1
            messages.append(m)
            amount -= 1
            if amount <= 0:
                break
            elif ctx.options.message_link and m.make_link(ctx.guild_id) == ctx.options.message_link.strip():
                break
        if ctx.options.message_link and amount <= 0:
            raise BotResponseError(f"Your linked message is not under the last {MAX_AMOUNT} messages")
        messages.remove(await answer.message())
        await channel.delete_messages(messages)


@loader.command
class CommandName(
    SlashCommand,
    name="name",
    description="description",
    dm_enabled=False,
    default_member_permissions=None,
    hooks=[sliding_window(3, 1, "user")]
):
    optional_string = lightbulb.string("message-link", "Delete until this message", default=None)
    optional_int = lightbulb.integer("amount", "The amount of messages you want to delete, Default: 5", default=None)

    @invoke
    async def purge(self, ctx: lightbulb.Context):
        ...



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
@lightbulb.app_command_permissions(hikari.Permissions.MANAGE_MESSAGES, bypass_checks=True)
@lightbulb.command("purge until here", "Delete all messages until the message (including)")
@lightbulb.implements(commands.MessageCommand)
async def purge_until_this_message(ctx: context.MessageContext):
    userid_to_amount: Dict[int, int] = {}
    message = await ctx.respond(f"Let me get the trash bin ready...\nY'know, this thing is pretty heavy")
    try:
        bot: Inu = ctx.bot
        message_id: int = ctx.options.target.id
        messages = []
        amount = 100
        async for m in ctx.get_channel().fetch_history():
            if m.author.id not in userid_to_amount:
                userid_to_amount[m.author.id] = 0
            userid_to_amount[m.author.id] += 1
            messages.append(m)
            amount -= 1
            if amount <= 0:
                break
            elif m.id == message_id:
                break
        if amount <= 0:
            raise BotResponseError(f"Your linked message is not under the last 50 messages")
        
        user_name_amount = []
        for user_id, amount in userid_to_amount.items():
            user_name_amount.append([
                    display_name_or_id(user_id, guild_id=ctx.guild_id),
                    amount
            ])
        user_name_amount.append(["Total", len(messages)])
        table = tabulate(user_name_amount, tablefmt="rounded_outline", headers=["User", "Amount"])
        delete_in = datetime.now() + timedelta(seconds=20)
        msg = await ctx.edit_last_response(
            f"I'll do it. Let me some time.\n```\n{table}\n```🗑️ <t:{delete_in.timestamp():.0f}:R>"
        )
        messages.remove(await message.message())
        await ctx.get_channel().delete_messages(messages)
        await asyncio.sleep((delete_in - datetime.now()).total_seconds())
        await msg.delete()


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
        return
    except hikari.BadRequestError:
        raise BotResponseError(
            (
                "Discord don't accept it.\n"
                "Maybe the new name is too long?"
            ),
            ephemeral=True
        )
    await ctx.respond(
        f"Added alias `{alias}` to {member.display_name}\nNew name: {nickname} {seperator} {alias}",
        flags=hikari.MessageFlag.EPHEMERAL,
    )


