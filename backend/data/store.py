"""SQLAlchemy mappings and explicit short transactions."""

from contextlib import contextmanager

from sqlalchemy import MetaData

from backend.data.database import database


class Store:
    def __init__(self, url):
        self.engine = database(url)
        metadata = MetaData()
        metadata.reflect(self.engine)
        self.tables = metadata.tables

    def __getitem__(self, table):
        return self.tables[table]

    @contextmanager
    def transaction(self, *, write=True):
        with self.engine.connect() as connection:
            dialect = connection.dialect.name
            if dialect == "postgresql" and not write:
                connection.execution_options(isolation_level="REPEATABLE READ")
            with connection.begin():
                if dialect == "sqlite":
                    connection.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")
                yield connection

