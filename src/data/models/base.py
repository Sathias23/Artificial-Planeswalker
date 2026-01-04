"""SQLAlchemy declarative base and model base class."""

from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(MappedAsDataclass, DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    Uses MappedAsDataclass for automatic dataclass generation and
    DeclarativeBase for SQLAlchemy ORM functionality.
    """

    pass
