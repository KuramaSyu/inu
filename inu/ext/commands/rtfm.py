from ast import alias
import traceback
import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging
import re
import zlib
import io
import os
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import aiohttp
from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari.messages import ButtonStyle
from hikari.impl.special_endpoints import ActionRowBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
import lightbulb.utils as lightbulb_utils
from lightbulb import commands, context
import hikari

from utils import Colors
from utils import Paginator

from core import getLogger, Inu

log = getLogger(__name__)

class SphinxObjectFileReader:
    """Reads Sphinx files (.inv)"""
    # copied from RoboDanny
    # Inspired by Sphinx's InventoryFileReader
    BUFSIZE = 16 * 1024

    def __init__(self, buffer):
        self.stream = io.BytesIO(buffer)


    def readline(self):
        return self.stream.readline().decode('utf-8')

    def skipline(self):
        self.stream.readline()

    def read_compressed_chunks(self):
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self):
        buf = b''
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b'\n')
            while pos != -1:
                yield buf[:pos].decode('utf-8')
                buf = buf[pos + 1:]
                pos = buf.find(b'\n')


class SpecificSphinxFileReader(SphinxObjectFileReader):
    def __init__(self, buffer, docs_url, auto=False) -> None:
        super().__init__(buffer=buffer)
        self.docs_url = docs_url
        self.inv_version = None
        self.project_name = None
        self.version = None
        self.result = None
        if auto:
            self.result = self.parse()

    def parse(self):
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result = {}
        # 1st line is inv version info
        self.inv_version = self.readline().rstrip()
        if self.inv_version != '# Sphinx inventory version 2':
            raise RuntimeError('Invalid objects.inv file version - Only version 2 is supported')

        # next line is "# Project: <name>"
        # then after that is "# Version: <version>"

        # 2nd line is project name
        self.project_name = self.readline().rstrip()[11:]
        # 3rd line is version of project
        self.version = self.readline().rstrip()[11:]

        # next line says if it's a zlib header
        line = self.readline()
        if 'zlib' not in line:
            raise RuntimeError('Invalid objects.inv file, not z-lib compatible.')

        # This code mostly comes from the Sphinx repository.
        entry_regex = re.compile(r'(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)')
        for line in self.read_compressed_lines():
            match = entry_regex.match(line.rstrip())
            if not match:
                continue

            name, directive, prio, location, dispname = match.groups()
            domain, _, subdirective = directive.partition(':')
            if directive == 'py:module' and name in result:
                # From the Sphinx Repository:
                # due to a bug in 1.1 and below,
                # two inventory entries are created
                # for Python modules, and the first
                # one is correct
                continue

            # Most documentation pages have a label
            if directive == 'std:doc':
                subdirective = 'label'

            if location.endswith('$'):
                location = location[:-1] + name

            key = name if dispname == '-' else dispname
            prefix = f'{subdirective}:' if domain == 'std' else ''

            if self.project_name == 'discord.py':
                key = key.replace('discord.ext.commands.', '').replace('discord.', '')

            result[f'{prefix}{key}'] = os.path.join(self.docs_url, location)

        return result


def search(search_for, iterable, *, key=None, max_distance: int = 1000, case_sensitive=False):
    found = []
    if not case_sensitive:
        search_for = search_for.lower()
    for item in iterable:
        if (start := item.lower().find(search_for)) >= 0:
            found.append((start, item))

    def sort_key(tup):
        return tup[0]

    return [name for distance, name in sorted(found, key=sort_key) if distance <= max_distance]


plugin = lightbulb.Plugin("Read the FUCKING manual", "Extends the commands with rtfm commands", include_datastore=True)
plugin.d.rtfm_cache = {}
plugin.d.docs = {
            'hikari-lightbulb': 'https://hikari-lightbulb.readthedocs.io/en/latest',
            'dpy-latest': 'https://discordpy.readthedocs.io/en/latest',
            'python': 'https://docs.python.org/3',
            'dpy-master': 'https://discordpy.readthedocs.io/en/master',
            'hikari': "https://www.hikari-py.dev",

}

def get_docs_url_from(key):
    return plugin.d.docs.get(key)

def get_docs_name_form(url):
    for key, value in plugin.d.docs.items():
        if value == url:
            return key
    return None

async def send_manual(ctx, key: Union[str, list], obj):
    urls = []
    results = []
    if isinstance(key, str):
        urls.append(key)
    else:
        urls = key
    for url in urls:
        if not plugin.d.rtfm_cache:
            await _update_rtfm_cache()
        docs = plugin.d.rtfm_cache[url]
        # cut out "discord." "ext." "commands." of obj
        if key == get_docs_url_from('dpy-latest'):
            obj = re.sub(r'^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)', r'\1', obj)

        if (res := search(obj, docs, max_distance=40)[:15]):
            results.append(res)
        else:
            # needed because the embed name is fetched by the urls index
            # since both lists are ordered same
            results.append([])

    nothing = True
    embeds = []
    for index, result in enumerate(results):
        if result == []:
            continue
        rtfm_embed = hikari.Embed()
        rtfm_embed.description = ""
        rtfm_embed.color = Colors.from_name("darkslateblue")
        for entry in result:
            try:
                rtfm_embed.description += f"[`{entry}`]({plugin.d.rtfm_cache[urls[index]][entry]})\n"
                nothing = False
            except KeyError:
                log.info(f"no url for '{entry}' found")
        if rtfm_embed.description != "":
            rtfm_embed.title = get_docs_name_form(urls[index])
            embeds.append(rtfm_embed)
    if nothing:
        return await ctx.respond("Nothing Found :/")
    paginator = Paginator(
        page_s=embeds,
        timeout=5*60,
    )
    await paginator.start(ctx)

async def _update_rtfm_cache() -> None:
    session = aiohttp.ClientSession(loop=asyncio.get_running_loop())
    for name, url in plugin.d.docs.items():
        try:
            async with session.get(url + "/objects.inv") as resp:
                if resp.status != 200:
                    raise RuntimeError(f"{url} can't be fetched. Exited with Error code {resp.status}")
                inv_file = SpecificSphinxFileReader(
                    await resp.read(),
                    url,
                    auto=True,
                )
                plugin.d.rtfm_cache[url] = inv_file.result
        except Exception:
            log.error(traceback.format_exc())
    await session.close()
    return

@plugin.command
@lightbulb.option("obj", "the thing you want to search")
@lightbulb.command("rtfm", "read(s) the fucking manual", aliases=["rtfd"])
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def rtfm(ctx: context.Context):
    """
    READ THE FUCKING MANUAL!
    Searches the docs for your given obj
    [optional]obj: the thing you want to search; Default: all
    """
    urls = []
    urls.append(get_docs_url_from('hikari'))
    urls.append(get_docs_url_from('hikari-lightbulb'))
    await send_manual(ctx, urls, ctx.options.obj)


@rtfm.child
@lightbulb.option("obj", "the thing you want to search")
@lightbulb.command("discod-py", "search discord py manual", aliases=["dpy"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def discord_py(ctx: context.Context):
    """
    Searches the latest Discord.py docs
    [optional]obj: the thing you want to search; Default: all
    """
    url = get_docs_url_from('dpy-latest')
    await send_manual(ctx, url, ctx.options.obj)

@rtfm.child
@lightbulb.option("obj", "the thing you want to search")
@lightbulb.command("hikari", "search hikari manual")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def _hikari(ctx: context.Context):
    """
    Searches the hikari and lightbulb docs
    [optional]obj: the thing you want to search; Default: all
    """
    urls = []
    urls.append(get_docs_url_from('hikari'))
    urls.append(get_docs_url_from('hikari-lightbulb'))
    await send_manual(ctx, urls, ctx.options.obj)

@rtfm.child
@lightbulb.option("obj", "the thing you want to search")
@lightbulb.command("python", "search Python manual", aliases=["py"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def python(ctx: context.Context):
    """
    Searches the Python docs
    [optional]obj: the thing you want to search; Default: all
    """
    url = get_docs_url_from('python')
    await send_manual(ctx, url, ctx.options.obj)

def load(bot: Inu):
    bot.add_plugin(plugin)
    bot.add_task(_update_rtfm_cache, hours=8)
    asyncio.create_task(_update_rtfm_cache)
