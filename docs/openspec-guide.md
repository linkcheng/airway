# OpenSpec 学习笔记

> 来源：https://github.com/Fission-AI/OpenSpec
> 整理日期：2026-06-06

## 核心理念

**规格驱动开发（Spec-Driven Development, SDD）** — 先对齐要建什么，再写代码。

- 需求规格持久化在代码仓库中，跨会话不丢失
- 每个 change 产出 proposal、design、tasks、spec delta，方便 review
- 轻量、迭代、不搞瀑布

```
fluid not rigid        → 随时更新任何 artifact，没有僵化的阶段门控
iterative not waterfall → 迭代式，不是瀑布式
brownfield-first       → 适合已有代码库，不假设从零开始
```

## 安装与初始化

```bash
# 前置：Node.js 20.19+
npm install -g @fission-ai/openspec@latest

# 在项目目录初始化
cd your-project
openspec init

# 升级
npm install -g @fission-ai/openspec@latest
openspec update   # 刷新 agent 指令
```

## 核心工作流（3 步闭环）

### 1. `/opsx:propose "需求描述"` — 提案

AI 自动搜索已有 specs 和代码库，生成 change 文件夹：

```
openspec/changes/add-dark-mode/
├── proposal.md   ← 为什么做、改什么
├── specs/        ← 规格变更（spec delta）
├── design.md     ← 技术方案
└── tasks.md      ← 实现任务清单
```

### 2. `/opsx:apply` — 实现

Agent 按 tasks.md 清单逐步写代码。

### 3. `/opsx:archive` — 归档

完成后归档到 `openspec/changes/archive/`，更新 specs。

## 扩展工作流

通过 `openspec config profile` 切换到扩展模式，额外命令：

| 命令 | 用途 |
|------|------|
| `/opsx:new` | 创建新 change |
| `/opsx:continue` | 继续未完成的 change |
| `/opsx:ff` | 快速前进 |
| `/opsx:verify` | 验证实现 |
| `/opsx:bulk-archive` | 批量归档 |
| `/opsx:onboard` | 项目 onboard |

## Spec 文件结构

按能力域组织，存放在 `openspec/specs/` 下：

```
openspec/specs/
├── auth-login/spec.md
├── auth-session/spec.md
└── checkout-payment/spec.md
```

每个 spec.md 格式：

```markdown
# <capability> Specification

## Purpose
<能力描述>

## Requirements

### Requirement: <需求名>
<需求描述>

#### Scenario: <场景名>
- GIVEN <前置条件>
- WHEN <触发条件>
- THEN <预期结果>
- AND <附加结果>
```

## Spec Delta（核心机制）

每次 change 展示需求的增删改，用 diff 格式：

```markdown
### Requirement: Session expiration
- The system SHALL expire sessions after a configured duration.
+ The system SHALL support configurable session expiration periods.
```

这使得 reviewer 能快速理解"系统需求发生了什么变化"，而不需要翻代码。

## 支持的 AI 工具

原生支持 20+ 工具（通过 slash commands 集成）：

Claude Code / Cursor / Codex / GitHub Copilot / Windsurf / Gemini CLI / Cline 等

## 与其他方案对比

| 方案 | 特点 |
|------|------|
| **OpenSpec** | 轻量、迭代式、specs 持久化在仓库 |
| **Spec Kit (GitHub)** | 更重量级，有僵化的阶段门控 |
| **Kiro (AWS)** | 锁定 AWS IDE 和 Claude 模型 |
| **不用 Spec** | 需求只在聊天历史中，不可预测 |

## 对 Airway 项目的使用方式

在 openspec 分支下：

```bash
# 1. 初始化
cd /Users/zhenglong/ai-native/rag/airway/openspec
openspec init

# 2. 定义需求
/opsx:propose "构建连接 Clawith Agent 与 Bisheng RAG 后端的无状态 MCP 代理"

# 3. 审查 proposal、design、tasks，调整后实现
/opsx:apply

# 4. 完成后归档
/opsx:archive
```

## 注意事项

- 推荐 Opus 4.7 / Codex 5.5 等高推理模型
- 保持干净的 context window，开始实现前清除上下文
- Specs 应该 check-in 到代码仓库，作为活的文档
- 不要试图一次性生成所有 specs，按需创建
