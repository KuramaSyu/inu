from utils.db import Database

class KeyValueDB:
    db: Database


class Table():
    def __init__(self, table_name: str):
        self.name = name