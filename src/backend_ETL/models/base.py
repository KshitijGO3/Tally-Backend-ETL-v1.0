"""Declarative base shared by all models."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    def to_dict(self) -> dict[str, Any]:
        """Column name -> value, matching the dict rows the raw-SQL code used to return."""
        return {c.name: getattr(self, c.key) for c in self.__table__.columns}
