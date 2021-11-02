# inu
A Discord bot written with hikari

# Preparations
## 1.
Install postgresql and create a database with name "inu_db"

## 2.
Create a ".env" file in the root dir and copy the text below in there:
```
DISCORD_BOT_TOKEN=x
DEFAULT_PREFIX=x

REDDIT_APP_ID=x
REDDIT_APP_SECRET=x

SPOTIFY_CLIENT_ID=x
SPOTIFY_CLIENT_SECRET=x

DSN_LINUX=postgresql://linux_profile_name:password@ip_address/inu_db
DSN=postgresql://linux_profile_name:password@ip_address/inu_db

```

## 3.
fill out every value with a `x` and correct `DSN_LINUX` and `DSN`

## 4.
copy a link of Lavalink.jar into /inu/data/music

## 5.
run the prepare.py file in the root dir
