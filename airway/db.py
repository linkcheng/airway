from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from airway.config import AppConfig


def create_session_factory(config: AppConfig) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(config.database.url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
