import asyncio
import logging
import typing
from datetime import datetime
from typing import *
import qrcode
from qrcode.image.styles.moduledrawers import GappedSquareModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from qrcode.image.styledpil import StyledPilImage
import io

import hikari
import lightbulb

from hikari import (
    ActionRowComponent, 
    Embed, 
    MessageCreateEvent, 
    embeds, 
    ResponseType, 
    TextInputStyle
)
from hikari.events import InteractionCreateEvent
from hikari.impl.special_endpoints import ActionRowBuilder, LinkButtonBuilder
from hikari.messages import ButtonStyle
from jikanpy import AioJikan
from lightbulb import OptionModifier as OM
from lightbulb import commands, context
from lightbulb.context import Context


from utils import (
    Colors, 
    Human, 
    Paginator, 
    Reddit, 
    Urban, 
    crumble
)
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger
)

log = getLogger(__name__)

plugin = lightbulb.Plugin("qrcode-generation", "Used to generate qr codes")
bot: Inu

@plugin.command
@lightbulb.option("content", "the content of the QR code", modifier=OM.CONSUME_REST)
@lightbulb.command("qrcode", "create an QR code")
@lightbulb.implements(commands.SlashCommand)
async def make_qr_code(ctx: context.Context):
    if len(ctx.options.content) > 180:
        raise BotResponseError(
            str(
                "QR code is too gigantic, that I could still display it well.\n"
                "You can generate big ones here: https://www.qrcode-generator.de/"
            ),
                ephemeral=True
        )
    bot: Inu = ctx.bot
    start = datetime.now()
    try:
        qr = qrcode.QRCode()
        qr.add_data(ctx.options.content)
        f = io.StringIO()
        qr.print_ascii(out=f)
    except qrcode.exceptions.DataOverflowError:
        raise BotResponseError("The content is too long to generate a QR code")
    ### code below is for a custom QR code png
    # f = io.StringIO()
    # qr.print_ascii(out=f)
    # f.seek(0)
    # text = f.read()
    # log.debug(text)
    # log.debug(f"length of qr code: {len(text)}")
    # if len(f.getvalue()) < 1800:
    #     return await ctx.respond(f"```{text}```")
    # f.seek(0)
    # qr.make(fit=True)
    # img = qr.make_image(
        # image_factory=StyledPilImage, 
        # # module_drawer=GappedSquareModuleDrawer(),
        # color_mask=SolidFillColorMask(
        #     back_color=(54, 57, 63),
        #     front_color=(160, 190, 255)
    #         front_color=(83, 101, 255)
    #     )
        
    # )
    # buffer = io.BytesIO()
    # png = img.save(buffer, format="PNG")
    # buffer.seek(0)
    # await ctx.respond(".", attachment=hikari.Bytes(buffer, "qrcode.png"))
    f.seek(0)
    text = f.read()
    if len(text) > 2000:
        raise BotResponseError(
            "This QR Code is too big, that Discord could handle it. I am sorry - maybe take a look here: https://www.qrcode-generator.de/", 
            ephemeral=True
        )
    await ctx.respond(f"```{text}```")
    
    




def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

