import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from airway.models.mapping import UserMapping


@pytest.mark.asyncio
async def test_create_user_mapping(db_session: AsyncSession):
    mapping = UserMapping(
        clawith_uid="u_abc123",
        bisheng_uid="42",
        bisheng_username="clawith_u_abc123",
    )
    db_session.add(mapping)
    await db_session.commit()
    await db_session.refresh(mapping)

    assert mapping.id is not None
    assert mapping.clawith_uid == "u_abc123"
    assert mapping.bisheng_uid == "42"
    assert mapping.created_at is not None


@pytest.mark.asyncio
async def test_find_mapping_by_clawith_uid(db_session: AsyncSession):
    mapping = UserMapping(
        clawith_uid="u_xyz",
        bisheng_uid="99",
        bisheng_username="clawith_u_xyz",
    )
    db_session.add(mapping)
    await db_session.commit()

    result = await db_session.execute(
        select(UserMapping).where(UserMapping.clawith_uid == "u_xyz")
    )
    found = result.scalar_one()
    assert found.bisheng_uid == "99"


@pytest.mark.asyncio
async def test_unique_clawith_uid(db_session: AsyncSession):
    from sqlalchemy.exc import IntegrityError

    m1 = UserMapping(clawith_uid="u_dup", bisheng_uid="1", bisheng_username="c_u_dup")
    db_session.add(m1)
    await db_session.commit()

    m2 = UserMapping(clawith_uid="u_dup", bisheng_uid="2", bisheng_username="c_u_dup2")
    db_session.add(m2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
