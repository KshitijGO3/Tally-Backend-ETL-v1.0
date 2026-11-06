"""Security, client and chat tables (declarative models)."""

from __future__ import annotations

import datetime as dt  # noqa: F401
import decimal  # noqa: F401

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend_ETL.models.base import Base


class Client(Base):
    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(Text)
    tally_version: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class ApiToken(Base):
    __tablename__ = "api_tokens"
    __table_args__ = (Index("idx_api_tokens_hash", "token_hash"),)

    token_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    client_id: Mapped[str | None] = mapped_column(Text, unique=True)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    token_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    last_used_at: Mapped[str | None] = mapped_column(Text)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_client", "client_id"),
    )

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[str] = mapped_column(
        Text, ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'viewer'"))
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    last_login_at: Mapped[str | None] = mapped_column(Text)


class ClientCompany(Base):
    __tablename__ = "client_companies"
    __table_args__ = (
        UniqueConstraint("client_id", "company_guid"),
        Index("idx_client_comp_lookup", "client_id", "company_guid"),
        Index("idx_client_comp_guid", "company_guid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    client_id: Mapped[str] = mapped_column(
        Text, ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False
    )
    company_guid: Mapped[str] = mapped_column(
        Text, ForeignKey("companies.guid", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class UserCompany(Base):
    __tablename__ = "user_companies"
    __table_args__ = (
        UniqueConstraint("user_id", "company_guid"),
        Index("idx_user_companies_lookup", "user_id", "company_guid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    company_guid: Mapped[str] = mapped_column(
        Text, ForeignKey("companies.guid", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("idx_chat_messages_lookup", "user_id", "company_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("companies.guid", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_called: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
