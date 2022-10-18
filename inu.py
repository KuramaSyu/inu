"""Small cli program for managing the bot"""

from typing import *
import os
import sys
from datetime import datetime
import subprocess
import time

import typer
from simple_term_menu import TerminalMenu
from rich.progress import track

__app_name__ = "INU"
__version__ = "0.1.0"

BACKUP_FOLDER = "../db_backup"
app = typer.Typer()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{__app_name__} v{__version__}")
        raise typer.Exit()
        

def get_file_size_in_mib(file_path) -> str:
   """ Get size of file at given path in MiB"""
   # get statistics of the file
   stat_info = os.stat(file_path)
   # get size of file in bytes
   size = stat_info.st_size
   return f"{size/1024/1024:.02f} MiB"


@app.command()
def backup(
    name: Optional[str] = typer.Option(
        None,
        "-n",
        "--name",
        help="add a custom name for the dump file"
    ),
    remove_timestamp: bool = typer.Option(
        False,
        "-r",
        "--rm-time",
        help="remove the timestamp from the file name"
    ),
) -> None:
    """make a backup"""
    now = datetime.now()
    file_name: str = name or "dump"
    if not remove_timestamp:
        file_name += f"-{now.year}-{now.month}-{now.day}T{now.hour:02d}-{now.minute:02d}-{now.second:02d}"
    file_name += ".sql"
    path = f"{BACKUP_FOLDER}/{file_name}"
    path = os.path.join(BACKUP_FOLDER, file_name)
    typer.secho(f"Creating backup: {BACKUP_FOLDER}/{file_name}", fg="green")
    try:
        os.mkdir(f"{BACKUP_FOLDER}")
        # open(path, 'a').close()
    except:
        pass
    exit_code = os.system(f"""docker exec -t postgresql pg_dumpall -c -U inu > "{path}" """)
    
    if exit_code != 0:
        typer.secho(f"Failed to create backup wiht code {exit_code}", fg="red")
        return
    typer.secho(f"Created {path} [{get_file_size_in_mib(path)}]", fg="green")



@app.command("restore")
def restore(
    pre_start_docker: bool = typer.Option(
        False,
        "-p",
        "--pre-start",
        "--pre-start-docker",
        "--ps",
        help="start docker if it is down"
    ),
    no_restart: bool = typer.Option(
        False,
        "-n"
        "--no-restart",
        "--nr",
        help="don't restart the bot after restoring the DB"
    ),
    docker_restart_args: str = typer.Option(
        "-d",
        "--docker-args",
        help="Args appended to `docker-compose up` when restarting. Default is -d"
    )
):
    """restore a backup"""
    files = [file for file in os.listdir(BACKUP_FOLDER) if os.path.isfile(os.path.join(BACKUP_FOLDER, file))]
    terminal_menu = TerminalMenu(files)
    menu_entry_index = terminal_menu.show()
    file_name = files[menu_entry_index]
    path = f"{BACKUP_FOLDER}/{file_name}"
    if pre_start_docker:
        os.system("docker-compose up -d")
        for value in track(range(100), description="Waiting 10 seconds.."):
            # Fake processing time
            time.sleep(0.1)
    typer.secho(f"restoring {file_name} [{get_file_size_in_mib(path)}]")
    exit_code = os.system(f"""
docker kill inu &&
docker exec -i postgresql psql -U inu inu_db -c "CREATE DATABASE temp;" ||
docker exec -i postgresql psql -U inu temp -c "DROP DATABASE inu_db;" ||
cat "{path}" | docker exec -i postgresql psql -U inu temp &&
docker exec -i postgresql psql -U inu inu_db -c "DROP DATABASE temp;"
""")
    if not no_restart:
        os.system(f"docker-compose up {docker_restart_args}")
    if exit_code != 0:
        typer.secho(f"Failed to create backup wiht code {exit_code}", fg="red")


@app.callback(invoke_without_command=True)
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=_version_callback,
    )
) -> None:
    pass
    

if __name__ == "__main__":
    app(prog_name="inu-cli")
    # typer.run(main)