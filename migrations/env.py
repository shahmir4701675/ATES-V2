"""Run Alembic with the explicitly supplied disposable database connection."""

from alembic import context

with context.config.attributes["engine"].connect() as connection:
    context.configure(connection=connection, transactional_ddl=True)
    with context.begin_transaction():
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        context.run_migrations()

