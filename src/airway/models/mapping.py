from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class UserMapping(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    clawith_uid: str = Field(index=True, unique=True)
    bisheng_uid: str
    bisheng_username: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
