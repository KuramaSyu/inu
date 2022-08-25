# Setup
1. copy the repo
2. copy the `config_template.yaml` file and rename it to `config.yaml`
3. Fill in all your credentials where you see a `X`
4. Download the Lavalink.jar file and put it into `dependencies/fred_boat/`

# Commands

## Docker and docker-compose
to start after making changes to config:

`docker-compose up --build`

to start without making changes:

`docker-compose up`

to enter the terminal and use psql:

`docker exec -it postgresql psql -U inu inu_db`

## Keyboard shortcuts

to move docker-compose into the background:

`ctrl + z`

## Database

to backup the database:

`docker exec -t <postgres-container-id> pg_dumpall -c -U inu > dump_file.sql`

to restore the dump:

`cat dump_file.sql | docker exec -i <postgres-container-id> psql -U inu inu_db`

"postgresql" can also be used instead of the id, hence it's the containers name

