from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.database import SessionLocal


def database_session() -> Generator[Session, None, None]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
