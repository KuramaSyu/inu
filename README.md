# Setup
```bash
# copy repo
git clone https://github.com/zp33dy/inu

cd inu
cp template-config.yaml config.yaml

# Set the Discord token in the config.yaml
# Set other with `XXX` or `000` filled fields in the config

# start the bot
docker compose up --build
```

# Commands

command | sub command | description
--------|-------------|-------------
tag | add | add a tag (same as a note)
tag | get | get a tag 
tag | edit | edit a tag (value / name / ...)
anime | | Shows information for an Anime
tv-show | | Shows information for a tv-show
movie | | Shows information about a movie
anime-of-the-week | | Shows which anime are popular this week
play | | play a song
current-games | | displays a chart with the games which where played during a specified time period (default 14d)
week-activity | | the same as `current-games` but with one chart summing it up

## `/current-games`
shows the last played games as a line chart. Example:
[![grafik.png](https://i.postimg.cc/8zgK5c1m/grafik.png)](https://postimg.cc/mtVNpb1P)

## `/week-activity`
Similar to `/current-games` but with one chart summing all games up:
[![grafik.png](https://i.postimg.cc/jShpYPz7/grafik.png)](https://postimg.cc/xXcxKkpf)

## `/anime {name}`
Shows information for an Anime
[![grafik.png](https://i.postimg.cc/RZ64p5Wm/grafik.png)](https://postimg.cc/QF32VzgY)

## Docker and docker-compose
to start after making changes to config:

`docker-compose up --build`

to start without making changes:

`docker-compose up`

to enter the terminal and use psql:

`docker exec -it postgresql psql -U inu inu_db`

## Database
### automatically
backup:
```bash
python inu.py backup
```

restore:
```bash
python inu.py restore
```
The restore command is interactive and lets you choose the dumb to restore
### manual
to backup the database:

`docker exec -t <postgres-container-id> pg_dumpall -c -U inu > dump_file.sql`
`docker exec -t postgresql pg_dumpall -c -U inu > dump_file.sql`

to restore the dump:

`cat dump_file.sql | docker exec -i <postgres-container-id> psql -U inu inu_db`

"postgresql" can also be used instead of the id, hence it's the containers name

to backup from ssh:
`ssh host@IP "docker exec -t postgresql pg_dumpall -c -U inu" > dump_file.sql`

