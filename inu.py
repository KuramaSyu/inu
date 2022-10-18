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
DEFAULT_NAME = "dump"
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
    ssh: Optional[str] = typer.Option(
        None,
        "--ssh",
        help="Host@IP to copy from",
    ),
    backup_folder: str = typer.Option(
        BACKUP_FOLDER,
        "--folder"
    )
) -> None:
    """make a backup"""
    now = datetime.now()
    file_name: str = name or DEFAULT_NAME
    if not remove_timestamp:
        file_name += f"-{now.year}-{now.month}-{now.day}T{now.hour:02d}-{now.minute:02d}-{now.second:02d}"
    file_name += ".sql"
    path = f"{backup_folder}/{file_name}"
    path = os.path.join(backup_folder, file_name)
    typer.secho(f"Creating backup: {path}", fg="green")
    try:
        os.mkdir(f"{backup_folder}")
        # open(path, 'a').close()
    except:
        pass
    base_cmd = f"""docker exec -t postgresql pg_dumpall -c -U inu"""
    if ssh:
        cmd = f"""ssh {ssh} "{base_cmd}" > {path}"""
    else:
        cmd = f"""{base_cmd} > {path}"""
    exit_code = os.system(cmd)
    
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
    ),
    backup_folder: str = typer.Option(
        BACKUP_FOLDER,
        "--folder"
    )
):
    """restore a backup"""
    files = [file for file in os.listdir(backup_folder) if os.path.isfile(os.path.join(backup_folder, file))]
    
    typer.secho(f"Select a backup from {backup_folder}", bold=True, fg="cyan")
    terminal_menu = TerminalMenu(files)
    menu_entry_index = terminal_menu.show()
    
    file_name = files[menu_entry_index]
    path = f"{backup_folder}/{file_name}"
    
    if pre_start_docker:
        os.system("docker-compose up -d")
        for value in track(range(100), description="Waiting 10 seconds.."):
            time.sleep(0.1)

    typer.secho(f"restoring {file_name} [{get_file_size_in_mib(path)}]")
    # make the actual backup
    exit_code = os.system(f"""
docker kill inu;
docker exec -i postgresql psql -U inu inu_db -c "CREATE DATABASE temp;";
docker exec -i postgresql psql -U inu temp -c "DROP DATABASE inu_db;";
cat "{path}" | docker exec -i postgresql psql -U inu temp;
docker exec -i postgresql psql -U inu inu_db -c "DROP DATABASE temp;"
    """)
    if not no_restart:
        os.system(f"docker-compose up {docker_restart_args}")
    if exit_code != 0:
        typer.secho(f"Failed to create backup wiht code {exit_code}", fg="red")



@app.command("clean")
def clean(
    keep_newest_n: Optional[int] = typer.Option(
        None,
        "-n",
        "--except-newest",
        "--keep-newest",
        help="delete everything except newest n"
    ),
    backup_folder: str = typer.Option(
        BACKUP_FOLDER,
        "--folder",
        help="the folder with backups"
    ),
    older_then: Optional[datetime] = typer.Option(
        None,
        "-o",
        "--older-then",
        help="delete all backups <older-then>"
    ),
    only_default_dumps: bool = typer.Option(
        False,
        "-d",
        "--only-default",
        help=f"Clean only default dumps starting with `{DEFAULT_NAME}`"
    ),
    when_contains: Optional[str] = typer.Option(
        None,
        "-c",
        "--contains",
        help=f"Clean only default dumps starting with `{DEFAULT_NAME}`"
    ),

):
    """restore a backup"""
    
    files: List[str] = [file for file in os.listdir(backup_folder) if os.path.isfile(os.path.join(backup_folder, file))]
    
    if only_default_dumps:
        files = [f for f in files if f.startswith(DEFAULT_NAME)]

    if when_contains:
        files = [f for f in files if when_contains in f]

    if keep_newest_n:
        files.sort(key=lambda f: os.path.getmtime(os.path.join(backup_folder, f)), reverse=True)
        to_delete = files[keep_newest_n:]
        for file in to_delete:
            path = os.path.join(backup_folder, file)
            os.remove(path)
            typer.secho(f"deleting {file}", fg="red")

    if older_then:
        older_then_timestamp = older_then.timestamp()
        for file in files:
            path = os.path.join(backup_folder, file)
            if (timestamp := os.path.getmtime(path)) < older_then_timestamp:
                typer.secho(f"deleting {file}", fg="red")
                os.remove(path)
    if not (
        keep_newest_n
        or older_then
    ):
        typer.secho(f"Manual select backups from {backup_folder}", bold=True, fg="cyan")
        terminal_menu = TerminalMenu(files, multi_select=True)
        menu_entry_indexes = terminal_menu.show()
        for i in menu_entry_indexes:
            os.remove(os.path.join(backup_folder, files[i]))
            typer.secho(f"deleted {files[i]}", fg="red")



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