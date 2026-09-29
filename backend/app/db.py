from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings


class Base(DeclarativeBase):
    pass


cfg = settings()
engine = create_engine(
    cfg.database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if cfg.database_url.startswith("sqlite") else {},
)
if cfg.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_pragmas(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")


SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
