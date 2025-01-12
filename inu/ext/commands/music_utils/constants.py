import re

# prefix for autocomplete history values
HISTORY_PREFIX = "History: "
MEDIA_TAG_PREFIX = "Media Tag: "
# if the bot is alone in a channel, then
DISCONNECT_AFTER = 60 * 10  # seconds
# REGEX for [title](url) markdown
MARKDOWN_URL_REGEX = re.compile(r"\[(.*?)\]\((https:\/\/.*?)\)")
URL_REGEX = re.compile(r"(https:\/\/.*?)")