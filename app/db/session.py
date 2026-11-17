from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import PROJECT_ROOT, get_settings

settings = get_settings()
url = make_url(settings.database_url)
is_sqlite = url.get_backend_name() == "sqlite"

if is_sqlite and url.database and url.database != ":memory:":
    database_path = Path(url.database)
    if not database_path.is_absolute():
        database_path = PROJECT_ROOT / database_path
    database_path = database_path.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    url = url.set(database=str(database_path))

engine = create_engine(
    url,
    connect_args={"check_same_thread": False} if is_sqlite else {},
)

if is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine)


def get_db() -> Iterator[Session]:
    """One session per request, always closed."""
    with SessionLocal() as db:
        yield db