from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, String
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.dialects.postgresql import ARRAY
import uuid
from typing import Optional, List
from datetime import datetime, timezone


def _utcnow() -> datetime:
    """Return timezone-naive UTC timestamp."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(SQLModel, table=True):
    __tablename__ = "users"

    uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    )
    email: str
    password_hash: str = Field(default="", exclude=True)
    user_name: str

    oauth_sessions: List["OAuthSession"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"lazy": "selectin"}
    )
    gmails: List["GoogleAccount"] = Relationship(
        back_populates="user_rel", sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(default_factory=_utcnow)


class GoogleAccount(SQLModel, table=True):
    __tablename__ = "google_accounts"

    uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    )
    user_uid: Optional[uuid.UUID] = Field(foreign_key="users.uid", index=True)
    user_rel: Optional["User"] = Relationship(back_populates="gmails")
    google_email: str
    access_token: str
    refresh_token: str
    token_expiry: datetime | None = None
    scope: List[str] = Field(sa_column=Column(ARRAY(String)))
    created_at: datetime = Field(default_factory=_utcnow)


class OAuthSession(SQLModel, table=True):
    __tablename__ = "oauth_sessions"

    id: int | None = Field(default=None, primary_key=True)

    user_uid: Optional[uuid.UUID] = Field(foreign_key="users.uid", index=True)
    user: Optional["User"] = Relationship(back_populates="oauth_sessions")
    state: str = Field(unique=True, index=True)
    code_verifier: str
    created_at: datetime = Field(default_factory=_utcnow)


class ChatState(SQLModel, table=True):
    __tablename__ = "chats"

    uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    )
    user_uid: Optional[uuid.UUID] = Field(foreign_key="users.uid", index=True)
    thread_id: str = Field(index=True)
    chat_title: str
    created_at: datetime = Field(default_factory=_utcnow)
