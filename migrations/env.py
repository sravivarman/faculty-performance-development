from alembic import context
from backend.db import Base, engine
from backend import models

target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(url=str(engine.url), target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        # SQLite batch alterations recreate tables. Disable FK enforcement only
        # on this migration connection, then verify all preserved references.
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
        violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"Migration left invalid foreign keys: {violations}")
        connection.commit()
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
