import os

from dotenv import load_dotenv, dotenv_values
import hikari

import lightbulb

conf = dotenv_values()
for key, value in conf.items():
    print(f"key: {key}\nvalue: {value}")

logs = {
    "version": 1,
    "incremental": True,
    "loggers": {
        "hikari": {"level": "INFO"},
        "hikari.ratelimits": {"level": "TRACE_HIKARI"},
        "lightbulb": {"level": "DEBUG"},
    },
}

bot = lightbulb.Bot(
    prefix="inu-",
    token=conf["DISCORD_BOT_TOKEN"],
    intents=hikari.Intents.ALL,
    logs=logs,
)

rest_app = hikari.RESTApp(
    max_rate_limit=1
)
async def create_rest_bot(rest_app: hikari.RESTApp):
    async with rest_app.acquire(token=conf["DISCORD_BOT_TOKEN"], token_type="Bot") as client:
        return await client.fetch_my_user()


def load_slash(bot: lightbulb.Bot):
    for extension in os.listdir(os.path.join(os.getcwd(), "extensions/slash")):
        if extension == "__init__.py" or not extension.endswith(".py"):
            continue
        bot.load_extension(f"extensions.slash.{extension[:-3]}")

def load_prefix(bot: lightbulb.Bot):
    for extension in os.listdir(os.path.join(os.getcwd(), "extensions/prefix")):
        if extension == "__init__.py" or not extension.endswith(".py"):
            continue
        bot.load_extension(f"extensions.prefix.{extension[:-3]}")

load_prefix(bot)
load_slash(bot)
bot.run()
