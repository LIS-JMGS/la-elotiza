"""Entorno de Alembic: usa la misma configuración y modelos que la API."""

from logging.config import fileConfig

from alembic import context

from la_elotiza_api import models  # noqa: F401  (registra las tablas)
from la_elotiza_api.config import Settings
from la_elotiza_api.db import Base, make_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
database_url = (
    config.get_main_option("sqlalchemy.url") or Settings.from_env().database_url
)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite no soporta ALTER TABLE completo; batch recrea la tabla.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
