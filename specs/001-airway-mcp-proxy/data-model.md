# Data Model: Airway MCP Proxy

**Branch**: `001-airway-mcp-proxy` | **Date**: 2026-06-07

## Entities

### UserMapping

Clawith 用户到 Bisheng 用户的映射关系。

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | `Integer` | PK, autoincrement | 主键 |
| clawith_user_id | `String(255)` | UNIQUE, NOT NULL, index | Clawith 用户唯一标识 |
| bisheng_user_id | `Integer` | NOT NULL | Bisheng 用户 ID |
| bisheng_user_name | `String(255)` | NOT NULL | Bisheng 用户名（冗余存储，便于调试） |
| status | `Enum(active, inactive)` | NOT NULL, default=active | 映射状态 |
| created_at | `DateTime` | NOT NULL, server_default=now | 创建时间 |
| updated_at | `DateTime` | NOT NULL, onupdate=now | 更新时间 |

**Relationships**: None（独立实体）

**State Transitions**:
```
[新建] → active
active → inactive（用户停用时）
inactive → active（重新激活时）
```

### KnowledgeBaseConfig

知识库配置，将 Bisheng 知识库映射为 Agent 可用的名称。

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | `Integer` | PK, autoincrement | 主键 |
| name | `String(255)` | UNIQUE, NOT NULL | Agent 侧显示名称（如 "company-faq"） |
| bisheng_knowledge_id | `Integer` | NOT NULL | Bisheng 知识库 ID |
| description | `Text` | nullable | 知识库描述 |
| enabled | `Boolean` | NOT NULL, default=true | 是否启用 |
| created_at | `DateTime` | NOT NULL, server_default=now | 创建时间 |
| updated_at | `DateTime` | NOT NULL, onupdate=now | 更新时间 |

**Relationships**: None（独立实体）

**Notes**: 知识库配置通过 YAML 配置文件管理，MVP 阶段此表可选。配置文件优先。

## Non-Persisted Entities

### BishengToken（Redis 缓存）

不持久化到数据库，存储在 Redis 中。

| Field | Redis Key | Type | TTL |
|-------|-----------|------|-----|
| access_token | `airway:bisheng:token` | string (JWT) | Bisheng token 过期时间 - 5min |
| public_key | `airway:bisheng:rsa_public_key` | string (PEM) | 1 hour |

## SQLAlchemy Model Skeleton

```python
from datetime import datetime
from enum import StrEnum
from sqlalchemy import String, Integer, Text, Boolean, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


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
```

## Alembic Migration Notes

- 初始迁移：创建 `user_mappings` 表
- `KnowledgeBaseConfig` 表在后续迭代添加（MVP 使用配置文件）
