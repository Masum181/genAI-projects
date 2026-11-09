"""SQLAlchemy declarative base shared by relational model definitions."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative models."""
