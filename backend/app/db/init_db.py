from app.db.base import Base
from app.db.connection import engine


def init_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
