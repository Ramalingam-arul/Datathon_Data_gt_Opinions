"""SQLAlchemy models for local dev/testing.
Column names intentionally mirror the Catalyst Data Store tables 1:1,
so the Catalyst adapter can reuse the same dicts.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "Users"

    # Catalyst auto-generates ROWID (bigint). Locally we emulate it.
    ROWID: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # bcrypt hash, never plaintext
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="analyst")  # analyst | admin | sho
    district: Mapped[str] = mapped_column(String(60), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    CREATEDTIME: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user")


class ChatSession(Base):
    __tablename__ = "ChatSessions"

    ROWID: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # uuid4 hex
    user_id: Mapped[int] = mapped_column(ForeignKey("Users.ROWID"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="New chat")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | archived
    # For hackathon speed: full message history as a JSON string
    # [{"role":"user","content":"...","ts":"..."}, {"role":"assistant",...}]
    messages_json: Mapped[str] = mapped_column(Text, default="[]")
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    CREATEDTIME: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="sessions")


class AuditLog(Base):
    """Every security-relevant action lands here — required for the
    'audit logs and traceability' hackathon criterion."""
    __tablename__ = "AuditLogs"

    ROWID: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_email: Mapped[str] = mapped_column(String(255), index=True, default="anonymous")
    actor_role: Mapped[str] = mapped_column(String(30), default="")
    action: Mapped[str] = mapped_column(String(50), index=True)   # LOGIN_SUCCESS, QUERY_SUBMITTED, ...
    resource: Mapped[str] = mapped_column(String(120), default="")  # e.g. session_id affected
    detail: Mapped[str] = mapped_column(Text, default="")
    CREATEDTIME: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Roles per hackathon requirement
ROLES = ["investigator", "analyst", "supervisor", "policymaker", "admin"]
# Who can see the audit trail
AUDIT_VIEW_ROLES = {"supervisor", "admin"}
