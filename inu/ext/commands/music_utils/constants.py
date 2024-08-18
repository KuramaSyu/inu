import re

# If True connect to voice with the hikari gateway instead of lavalink_rs's
HIKARI_VOICE = True

# prefix for autocomplete history values
HISTORY_PREFIX = "History: "
MEDIA_TAG_PREFIX = "Media Tag: "
# if the bot is alone in a channel, then
DISCONNECT_AFTER = 60 * 10  # seconds
# REGEX for [title](url) markdown
MARKDOWN_URL_REGEX = re.compile(r"\[(.*?)\]\((https:\/\/.*?)\)")