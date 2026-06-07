# SpecKit (spec-kit) 使用教程

GitHub 出品的规格驱动开发（Spec-Driven Development）框架，配合 Claude Code 使用。

## 核心理念

传统开发：直接写代码 → 事后补文档
SpecKit：先写规格 → 再生成代码

规格（Spec）是一等公民，代码是规格的产出物。

## 安装

### 前置条件

- Python 3.11+
- uv（包管理）
- Claude Code
- Git

### 安装 specify CLI

```bash
# 指定稳定版本（推荐，替换 vX.Y.Z 为最新 release tag）
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z

# 或安装最新 main 分支
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# 验证
specify --version
```

### 管理命令

```bash
specify self check           # 检查是否有新版本
specify self upgrade         # 升级到最新版
specify self upgrade --tag vX.Y.Z  # 升级到指定版本
```

## 项目初始化

### 新项目

```bash
specify init my-project --integration claude
cd my-project
```

### 已有项目（当前目录）

```bash
specify init . --integration claude --force
```

### 可用的 integration

`claude`、`copilot`、`gemini`、`codex`、`cursor-agent`、`cline`、`roo`、`windsurf` 等 30+ 种。

### 初始化后的目录结构

```
.
├── .specify/
│   ├── memory/
│   │   └── constitution.md      # 项目原则
│   ├── scripts/
│   │   └── bash/
│   │       ├── check-prerequisites.sh
│   │       ├── create-new-feature.sh
│   │       ├── setup-plan.sh
│   │       └── setup-tasks.sh
│   └── templates/
│       ├── plan-template.md
│       ├── spec-template.md
│       └── tasks-template.md
├── .claude/
│   └── commands/
│       └── speckit-*.md         # Claude Code slash commands
└── specs/                       # 规格文件目录
```

## 开发工作流

共 6 步，按顺序执行。在 Claude Code 中使用 `/speckit.*` slash 命令。

### 第 1 步：建立项目原则

```
/speckit.constitution 描述你的项目原则
```

**做什么**：定义项目的开发准则，写入 `.specify/memory/constitution.md`。
**为什么**：后续所有步骤都以此为决策依据。

示例：
```
/speckit.constitution Python 3.12 项目，使用 FastMCP 框架，
遵循 SOLID 原则，测试覆盖率 > 80%，优先简洁实现，不过度设计
```

### 第 2 步：编写功能规格

```
/speckit.specify 描述你要构建什么
```

**做什么**：定义要构建的产品功能，生成 `specs/001-xxx/spec.md`。
**注意**：只关注 **what & why**，不要涉及技术栈。

示例：
```
/speckit.specify 构建一个 MCP 代理服务，连接 AI Agent 与 RAG 后端。
支持知识库查询、文档上传、用户身份映射。Agent 通过标准 MCP 协议调用，
无需了解后端 API 细节。
```

**产出**：
- 自动创建分支（如 `001-xxx`）
- 生成 `specs/001-xxx/spec.md`（用户故事 + 功能需求）

### 第 3 步：澄清需求（推荐但可选）

```
/speckit.clarify
```

**做什么**：系统性地提问，澄清规格中的模糊之处。
**什么时候用**：在 `/speckit.plan` 之前运行，减少返工。

### 第 4 步：制定技术方案

```
/speckit.plan 指定技术栈和架构
```

**做什么**：基于规格制定技术实现计划。
**这时才讨论技术选型**。

示例：
```
/speckit.plan Python 3.12 + FastMCP + httpx + pydantic-settings。
Bisheng 适配器模式，JWT 认证，YAML 配置，pytest 测试。
```

**产出**：
- `specs/001-xxx/plan.md`（实施计划）
- `specs/001-xxx/data-model.md`（数据模型）
- `specs/001-xxx/research.md`（技术调研）
- `specs/001-xxx/quickstart.md`（快速上手）

### 第 5 步：拆分任务

```
/speckit.tasks
```

**做什么**：将计划拆分为可执行的任务列表，生成 `specs/001-xxx/tasks.md`。

**产出特点**：
- 按用户故事组织任务
- 标注依赖关系
- 可并行的任务标记 `[P]`
- 包含文件路径和测试要求

### 第 6 步：执行实现

```
/speckit.implement
```

**做什么**：按任务列表顺序执行，实现代码。

**行为**：
- 验证前置条件（constitution、spec、plan、tasks）
- 按顺序执行任务
- 遵循 TDD 方式（如任务中定义）
- 提供进度更新

## 辅助命令

| 命令 | 用途 | 时机 |
|------|------|------|
| `/speckit.clarify` | 澄清需求 | specify 之后、plan 之前 |
| `/speckit.analyze` | 交叉检查一致性 | tasks 之后、implement 之前 |
| `/speckit.checklist` | 生成质量检查清单 | 需求验证 |

## 扩展与定制

### 扩展（Extensions）

添加新能力（如 Jira 集成、代码审查）：

```bash
specify extension search      # 搜索可用扩展
specify extension add <name>  # 安装扩展
```

### 预设（Presets）

定制现有工作流（如合规模板、术语定制）：

```bash
specify preset search         # 搜索可用预设
specify preset add <name>     # 安装预设
```

### 优先级（高到低）

1. `.specify/templates/overrides/` — 项目本地覆盖
2. `.specify/presets/templates/` — 已安装预设
3. `.specify/extensions/templates/` — 已安装扩展
4. `.specify/templates/` — SpecKit 内置默认

## 常见问题

### Q: 版本号怎么看？

去 [Releases](https://github.com/github/spec-kit/releases) 页面查看最新 tag。

### Q: 可以跳过某一步吗？

可以，但推荐完整走完。如果只是快速原型，可以在 specify 后直接 implement。

### Q: 如何处理已有项目？

用 `specify init . --force --integration claude` 在已有目录初始化。

### Q: PyPI 上的 specify-cli 是官方的吗？

不是。官方只从 `github.com/github/spec-kit` 安装。

---

参考：[github/spec-kit](https://github.com/github/spec-kit)
