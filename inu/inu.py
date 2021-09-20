import os
import asyncio

from dotenv import dotenv_values
import hikari

import lightbulb

conf = dotenv_values()
for key, value in conf.items():
    print(f"key: {key}\nvalue: {value}")
print(os.getcwd())
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

class Inu(lightbulb.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_prefix()
        self.load_slash()

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if not (loop := asyncio.get_running_loop()):
            raise RuntimeError("Eventloop could not be returned")
        return loop

    @property
    def me(self) -> hikari.User:
        if not (user := self.cache.get_me()):
            raise RuntimeError("Own user can't be accessed from cache")
        return user

    @property 
    def user(self) -> hikari.User:
        return self.me

    def load_slash(self):
        for extension in os.listdir(os.path.join(os.getcwd(), "inu/ext/slash")):
            if extension == "__init__.py" or not extension.endswith(".py"):
                continue
            bot.load_extension(f"ext.slash.{extension[:-3]}")

    def load_prefix(self):
        for extension in os.listdir(os.path.join(os.getcwd(), "inu/ext/prefix")):
            if extension == "__init__.py" or not extension.endswith(".py"):
                continue
            bot.load_extension(f"ext.prefix.{extension[:-3]}")

inu = Inu(
    prefix="inu-",
    token=conf["DISCORD_BOT_TOKEN"],
    intents=hikari.Intents.ALL,
    logs=logs,
)
inu.run()