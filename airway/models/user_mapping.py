from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MappingStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class UserMapping(Base):
    __tablename__ = "user_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clawith_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    bisheng_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    bisheng_user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[MappingStatus] = mapped_column(
        Enum(MappingStatus), nullable=False, default=MappingStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
