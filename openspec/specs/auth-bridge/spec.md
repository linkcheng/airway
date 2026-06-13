# auth-bridge Specification

## Purpose
TBD - created by archiving change airway-mvp. Update Purpose after archive.
## Requirements
### Requirement: Service Account 认证

Airway SHALL 使用配置的 Bisheng service account JWT token 调用 Bisheng API，token 通过 Cookie header 传递。

#### Scenario: 使用 service account token 调用 API

- **WHEN** Airway 向 Bisheng 发起 API 请求
- **THEN** 请求 header 中包含 Cookie 字段，值为 `access_token=<configured-token>`

### Requirement: Token 过期处理

Airway SHALL 检测 Bisheng API 返回的 401 状态码，并尝试自动刷新 token。

#### Scenario: Token 有效时正常请求

- **WHEN** Bisheng API 返回 2xx 状态码
- **THEN** 正常返回结果，不做额外处理

#### Scenario: Token 过期时尝试刷新

- **WHEN** Bisheng API 返回 401 状态码
- **THEN** Airway 使用配置的凭据重新登录获取新 token，更新内存中的 token，重试原请求

#### Scenario: 刷新失败时返回错误

- **WHEN** Token 刷新请求也失败（如凭据无效）
- **THEN** Airway 返回 MCP 错误响应，包含 "Authentication failed" 信息

### Requirement: 用户 ID 透传

Airway SHALL 接受可选的 user_id 参数，记录到请求日志中，用于审计追踪。

#### Scenario: 传入 user_id

- **WHEN** MCP tool 调用参数中包含 user_id
- **THEN** Airway 将该 user_id 记录到请求日志中，但不传递给 Bisheng API

#### Scenario: 未传入 user_id

- **WHEN** MCP tool 调用参数中不包含 user_id
- **THEN** Airway 正常执行请求，日志中 user_id 为空

