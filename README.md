# inu
A Discord bot with many commands written with hikari-py

# Preparations
## 1
Create a ".env" file in the root dir and copy the text below in there:
```
DISCORD_TOKEN=x
DEFAULT_PREFIX=x

REDDIT_APP_ID=x
REDDIT_APP_SECRET=x

SPOTIFY_CLIENT_ID=x
SPOTIFY_CLIENT_SECRET=x

DSN=postgresql://linux_profile_name:password@ip_address/inu_db

LAVALINK_IP=0.0.0.0  # change if needed
LAVALINK_PASSWORD=x  # needs to be the same like in the application.yml file

```
## 2
fill out every value with a `x` and correct `DSN_LINUX` and `DSN`
## 3
copy your `application.yml` file (for lavalink) into

root/dependencies/music

and

root/dependencies/fredboat

## 4
install java jdk and python

# Boot the bot with docker
## 1
install docker and docker-compose

go into the projects root directory (the dir with the `docker-compose.yml` file)

## 2
change the `LAVALINK_IP` in the `.env` file to `LAVALINK_IP=inu-lava-1`

## 3
start with:

> cd path/to/the/root/dir/with/docker-compose.yml

> docker-compose up --build

end with:

> docker-compose down inu

or

> `ctrl + c`  to interupt the process 
### NOTE:
docker was tested on arch linux and windows 10. Windows 10 wont work! So be sure to only use docker when you are in a linux enviroment

# Boot the bot on your machine

## 1
Install postgresql and create a database with name "inu_db"

## 2
Copy the `Lavalink.jar` file into `root/dependencies/music` folder

## 3
Run the prepare.py file in the root directory

## 4
make sure postgresql is running
## 5
Run
> python3 inu/main.py & java -jar dependencies/music/Lavalink.jar

to start the bot and the Lavalink server

End it with `ctrl + c` to interupt it


