"""Small cli program for managing the bot"""

from typing import *
import os
import sys
from datetime import datetime
import subprocess

import typer

__app_name__ = "INU"
__version__ = "0.1.0"

BACKUP_FOLDER = "../db_backup"
app = typer.Typer()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{__app_name__} v{__version__}")
        raise typer.Exit()

def backup_callback(v):
    """make a backup"""
    typer.secho("Creating backup...")
    now = datetime.now()
    file_name = f"pg_dump-{now.year}-{now.month}-{now.day}T{now.hour}-{now.minute}-{now.second}.sql"
    try:
        os.mkdir(f"{BACKUP_FOLDER}")
        open(f"{BACKUP_FOLDER}/{file_name}", 'a').close()
    except:
        pass
    cmd = f"docker exec -t postgresql pg_dumpall -c -U inu > {BACKUP_FOLDER}/{file_name}".split()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, err = p.communicate()
    if err:
    #os.system(f"docker exec -t postgresql pg_dumpall -c -U inu > {BACKUP_FOLDER}/{file_name}")
        typer.secho(f"Backup created: {BACKUP_FOLDER}/{file_name}", fg="green")



@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=_version_callback,
    ),
    backup: Optional[bool] = typer.Option(
        None,
        "--backup",
        "-b",
        help="Backup the bots Database",
        callback=backup_callback,
    )
) -> None:
    return
    

if __name__ == "__main__":
    #app(prog_name="inu-cli")
    if not os.geteuid() == 0:
        print("You need root")
        exit()
    typer.run(main)