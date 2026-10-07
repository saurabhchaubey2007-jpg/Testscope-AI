from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from apps.api.app.core.config import settings
from apps.api.app.core.database import Base
import apps.api.app.models  # noqa: F401  (register all tables)

config = context.config

# Only configure logging when invoked from the CLI (avoid clobbering the app's logging)
if config.config_file_name is not None and not config.attributes.get("skip_logging_config"):
    if context.config.get_main_option("sqlalchemy.url") in (None, "", "driver://user:pass@localhost/dbname"):
        fileConfig(config.config_file_name)

if not config.get_main_option("sqlalchemy.url") or config.get_main_option("sqlalchemy.url").startswith("driver://"):
    config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite can't ALTER most things; batch mode recreates tables instead
            render_as_batch=connection.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
