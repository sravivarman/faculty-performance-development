import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'faculty.db'}")
EVIDENCE_ROOT = Path(os.getenv("EVIDENCE_ROOT", str(ROOT / "storage" / "evidence")))
(ROOT / "data").mkdir(exist_ok=True)


class Base(DeclarativeBase):
    pass


def make_engine(url):
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")

    return engine


engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def sqlite_database_path(session):
    """Read the actual connection's main database path, not a guessed URL."""
    rows = session.connection().exec_driver_sql("PRAGMA database_list").all()
    filename = next(row[2] for row in rows if row[1] == "main")
    return str(Path(filename).resolve()) if filename else ":memory:"


def get_db():
    with SessionLocal() as session:
        yield session
