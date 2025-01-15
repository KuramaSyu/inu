from doctest import DocTestSuite
import traceback
import typing
from typing import (
    Iterable,
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
from hikari import ButtonStyle
from hikari.impl.special_endpoints import MessageActionRowBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
import lightbulb.utils as lightbulb_utils
from lightbulb import AutocompleteContext, commands, context, SlashCommand, invoke, invoke
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from fuzzywuzzy import fuzz
from cachetools import LRUCache, cached

from utils import Colors
from utils import Paginator

from core import getLogger, Inu, InuContext

log = getLogger(__name__)

loader = lightbulb.Loader()
bot: Inu = Inu.instance


rtfm_cache = {}
DOCS = {
    'hikari-lightbulb': 'https://hikari-lightbulb.readthedocs.io/en/latest',
    'python': 'https://docs.python.org/3',
    'hikari': "https://www.hikari-py.dev",
}
#### AUTOCOMPLETE ####

async def rtfm_autocomplete(
    option: hikari.AutocompleteInteractionOption, 
    docs: List[str]
) -> List[str]:
    if not rtfm_cache:
        await _update_rtfm_cache()
    results = search(
        search_for=option.value,
        docs=tuple(docs),
    )
    return [dict_["item"] for dict_ in results]


async def autocomplete_python(
    ctx: AutocompleteContext
) -> None:
    await ctx.respond(await rtfm_autocomplete(ctx.focused, ["python"])
) 

async def autocomplete_hikari(
    ctx: AutocompleteContext
) -> None:
    await ctx.respond(await rtfm_autocomplete(ctx.focused, ["hikari", "hikari-lightbulb"]))

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

@cached(LRUCache(128*1024))
def search(search_for, docs: tuple, case_sensitive=True):
    found = []
    # if not case_sensitive:
    #     search_for = search_for.lower()
    # for item in iterable:
    #     if (start := item.lower().find(search_for)) >= 0:
    #         found.append((start, item))
    iterable = [item for d in docs for item in rtfm_cache[DOCS[d]]]
    ratios = []
    for item in iterable:
        r = fuzz.token_sort_ratio(search_for, item)
        if r > 40 or search_for in item:
            ratios.append({"item": item, "ratio": r})
    if (new_r := [r for r in ratios if search_for in r["item"]]):
        ratios = new_r
    def sort_key(tup):
        return tup[0]

    # return [name for distance, name in sorted(found, key=sort_key) if distance <= max_distance]
    ratios.sort(key=lambda d: d["ratio"], reverse=True)
    return ratios[:24]

# Initialize cache dict


async def init_rtfm():
    try:
        await asyncio.sleep(10)
        trigger = IntervalTrigger(hours=8)
        bot.scheduler.add_job(_update_rtfm_cache, trigger)
        log.info(f"scheduled {_update_rtfm_cache.__name__}: {trigger}", prefix="init")
    except Exception:
        log.critical(traceback.format_exc())

rtfm_group = lightbulb.Group(name="rtfm", description="READ THE FUCKING MANUAL!")

@rtfm_group.register
class Rtfm(
    SlashCommand, 
    name="all",
    description="search all manuals",
    dm_enabled=True
):
    obj = lightbulb.string("obj", "the thing you want to search")

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await send_manual(ctx, ["hikari", 'hikari-lightbulb'], self.obj)

@rtfm_group.register
class RtfmHikari(
    SlashCommand,
    name="hikari",
    description="search hikari manual",
    dm_enabled=True
):
    obj = lightbulb.string("obj", "the thing you want to search", autocomplete=autocomplete_hikari)

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await send_manual(ctx, ["hikari", 'hikari-lightbulb'], self.obj)




@rtfm_group.register
class RtfmPython(
    SlashCommand,
    name="python",
    description="search Python manual",
    dm_enabled=True
):
    obj = lightbulb.string("obj", "the thing you want to search", autocomplete=autocomplete_python)

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await send_manual(ctx, ["python"], self.obj)



# Schedule the cache update job when bot starts
@loader.listener(hikari.StartedEvent)
async def on_ready(_: hikari.StartedEvent):
    await init_rtfm()

def get_docs_url_from(key):
    return DOCS.get(key)

def get_docs_name_form(url):
    for key, value in DOCS.items():
        if value == url:
            return key
    return None

async def send_manual(ctx, key: Union[str, list], obj):
    if not rtfm_cache:
        await _update_rtfm_cache()
    keys = []
    results = []
    if isinstance(key, str):
        keys.append(key)
    else:
        keys = key
    for key in keys:
        if (res := search(obj, tuple([key]))[:15]):
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
        for dict_ in result:
            entry = dict_["item"]
            try:
                rtfm_embed.description += f"[`{entry}`]({rtfm_cache[get_docs_url_from(keys[index])][entry]})\n"
                nothing = False
            except KeyError:
                log.info(f"no url for '{entry}' found")
        if rtfm_embed.description != "":
            rtfm_embed.title = get_docs_name_form(keys[index])
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
    for name, url in DOCS.items():
        try:
            async with session.get(url + "/objects.inv") as resp:
                if resp.status != 200:
                    raise RuntimeError(f"{url} can't be fetched. Exited with Error code {resp.status}")
                inv_file = SpecificSphinxFileReader(
                    await resp.read(),
                    url,
                    auto=True,
                )
                rtfm_cache[url] = inv_file.result
        except Exception:
            log.error(traceback.format_exc())
    await session.close()
    return



loader.command(rtfm_group)




