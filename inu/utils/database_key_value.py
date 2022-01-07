from utils.db import Database

class KeyValueDB:
    db: Database


class Table():
    def __init__(self, table_name: str):
        self.name = table_name

    async def insert(self, *values):
        pass