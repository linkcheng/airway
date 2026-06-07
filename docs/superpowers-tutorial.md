# Superpowers 插件使用教程

> 本教程面向 Airway superpower 分支开发者，系统讲解 superpowers 插件的核心概念、完整工作流和每个 skill 的用法。

## 目录

1. [概述](#1-概述)
2. [核心概念](#2-核心概念)
3. [完整工作流](#3-完整工作流)
4. [Skill 详解](#4-skill-详解)
5. [实战案例：Airway MCP Server](#5-实战案例airway-mcp-server)
6. [常见问题](#6-常见问题)

---

## 1. 概述

Superpowers 是 Claude Code 的结构化开发插件，通过一组 skill 强制执行"设计先行 → 测试驱动 → 代码审查"的开发纪律。它的核心价值：

- **防止跳步**：每个阶段都有"硬门禁"，未完成上一步就无法进入下一步
- **质量保证**：TDD 红绿灯循环、两阶段代码审查
- **上下文隔离**：每个任务用独立 subagent，避免上下文污染
- **可追溯**：所有设计文档和计划保存在 `docs/superpowers/` 目录

## 2. 核心概念

### 2.1 Skill

Skill 是 superpowers 插件提供的可调用指令，通过 `/skill-name` 或自动触发。核心 skill 有 14 个，按用途分为四类：

| 类别 | Skill | 用途 |
|------|-------|------|
| **设计** | `brainstorming` | 需求澄清与方案探索 |
| **计划** | `writing-plans` | 生成分步实现计划 |
| **执行** | `executing-plans` | 批量执行计划中的任务 |
| | `subagent-driven-development` | 每个 task 启动独立 subagent |
| | `dispatching-parallel-agents` | 并行派发多个 subagent |
| **测试** | `test-driven-development` | RED-GREEN-REFACTOR 循环 |
| | `systematic-debugging` | 4 阶段根因分析 |
| | `verification-before-completion` | 验证修复是否真正生效 |
| **审查** | `requesting-code-review` | 派发代码审查 subagent |
| | `receiving-code-review` | 处理审查反馈 |
| **收尾** | `finishing-a-development-branch` | 合并/PR 决策 |
| | `using-git-worktrees` | 创建隔离开发分支 |
| **其他** | `writing-skills` | 创建新 skill |
| | `using-superpowers` | 入口 skill，建立使用规则 |

### 2.2 Specs（设计文档）

Spec 是 brainstorming 阶段的产出，保存在 `docs/superpowers/specs/`。它定义：

- 背景与目标
- 架构方案（含技术选型）
- 模块划分
- 约束条件

### 2.3 Plans（实现计划）

Plan 是 `writing-plans` 阶段的产出，保存在 `docs/superpowers/plans/`。它将 spec 拆解为：

- 离散的 task（每个 2-5 分钟）
- 每个 task 包含：涉及的文件、完整的测试代码、完整的实现代码、验证命令
- 用 checkbox `- [ ]` 跟踪进度

### 2.4 优先级规则

当 skill 指令与用户指令冲突时：

```
用户指令 (CLAUDE.md / 直接要求) > superpowers skill > 默认系统行为
```

## 3. 完整工作流

```
需求输入
  │
  ▼
┌─────────────────────────────────────────────┐
│ 1. brainstorming                             │
│    苏格拉底式提问，探索需求，产出 spec        │
│    硬门禁：spec 必须获得用户批准              │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 2. writing-plans                             │
│    将 spec 拆解为 task 列表，产出 plan        │
│    硬门禁：plan 必须获得用户批准              │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 3. 执行（二选一）                             │
│                                              │
│   executing-plans（顺序执行）                 │
│   ┌─────────────────────────────────┐        │
│   │ 每个 task:                       │        │
│   │   a. TDD: 写失败测试 → 实现 → 通过│        │
│   │   b. requesting-code-review      │        │
│   │   c. 通过 → 下一个 task          │        │
│   └─────────────────────────────────┘        │
│                                              │
│   subagent-driven-development（并行执行）     │
│   ┌─────────────────────────────────┐        │
│   │ 每个 task 派发独立 subagent:      │        │
│   │   a. TDD + 两阶段审查             │        │
│   │   b. 审查通过 → 合并              │        │
│   │   c. 审查失败 → 重做              │        │
│   └─────────────────────────────────┘        │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 4. finishing-a-development-branch            │
│    验证全量测试 → 合并/PR/保留分支            │
└─────────────────────────────────────────────┘
```

## 4. Skill 详解

### 4.1 brainstorming — 需求澄清

**触发时机**：任何新功能开发、架构设计、行为修改之前。

**做什么**：
1. 通过提问探索用户真实意图
2. 提出 2-3 个方案并分析利弊
3. 产出设计 spec（保存到 `docs/superpowers/specs/`）
4. 等待用户确认

**产出格式**：
```
docs/superpowers/specs/YYYY-MM-DD-{feature-name}-design.md
```

**关键原则**：不能跳过。即使用户说"直接开始写代码"，也必须先完成 brainstorming。

### 4.2 writing-plans — 拆解任务

**触发时机**：spec 获得批准后。

**做什么**：
1. 将 spec 拆解为独立的 task
2. 每个 task 包含：
   - 涉及的文件列表
   - 完整的测试代码（先写）
   - 完整的实现代码
   - 验证命令和期望输出
   - 提交信息
3. 用 `- [ ]` checkbox 跟踪进度

**产出格式**：
```
docs/superpowers/plans/YYYY-MM-DD-{feature-name}.md
```

**task 粒度**：每个 task 应该 2-5 分钟可完成。如果一个 task 超过 5 分钟，拆分它。

### 4.3 test-driven-development — TDD 循环

**触发时机**：编写任何功能代码或修复 bug 时。

**做什么**：严格执行 RED-GREEN-REFACTOR：

```
RED    → 写一个会失败的测试，确认它失败
GREEN  → 写最少的代码让测试通过，不多不少
REFACTOR → 清理代码（仅在测试通过后）
```

**硬门禁**：
- 不能在测试之前写生产代码
- 如果发现代码写在测试之前，删除代码，重写测试
- 每次循环结束运行全量测试

### 4.4 executing-plans — 顺序执行

**触发时机**：plan 获得批准后。

**做什么**：
1. 按 plan 中 task 的顺序逐个执行
2. 每个 task 内部遵循 TDD
3. 每个 task 完成后做代码审查
4. 审查通过 → 标记 checkbox 并进入下一个
5. 审查失败 → 修复后重新审查

**适用场景**：task 之间有依赖关系，需要顺序执行。

### 4.5 subagent-driven-development — 并行执行

**触发时机**：plan 中的 task 之间相互独立时。

**做什么**：
1. 为每个 task 启动独立的 subagent
2. subagent 在隔离环境中完成 TDD + 代码审查
3. 两阶段审查：
   - 第一阶段：spec 符合性检查
   - 第二阶段：代码质量审查
4. 审查通过 → 合并结果
5. 审查失败 → subagent 重做

**适用场景**：task 之间无依赖，可以并行（如多个独立模块开发）。

### 4.6 requesting-code-review — 代码审查

**触发时机**：每个 task 完成后。

**做什么**：
1. 派发独立 subagent 审查代码
2. 审查维度：
   - 是否符合 spec 定义
   - 是否遵循 TDD 流程
   - 代码质量和安全性
3. 严重度分级：
   - **Critical**：阻塞后续工作
   - **Major**：需要修复
   - **Minor**：建议改进

### 4.7 systematic-debugging — 系统调试

**触发时机**：遇到 bug、测试失败、意外行为时。

**做什么**：4 阶段根因分析：
1. **捕获**：精确复现问题
2. **诊断**：从症状追溯根因
3. **修复**：最小化修改
4. **验证**：确认修复有效且无副作用

**关键原则**：不能猜测。必须先复现、诊断，再修复。

### 4.8 verification-before-completion — 完成验证

**触发时机**：标记任务完成之前。

**做什么**：
1. 运行全量测试
2. 检查是否满足 spec 中的所有要求
3. 确认没有引入回归

### 4.9 using-git-worktrees — 隔离开发

**触发时机**：开始新功能开发前。

**做什么**：
1. 创建 git worktree（隔离的工作目录）
2. 在新分支上开发
3. 开发完成后合并或丢弃

### 4.10 finishing-a-development-branch — 收尾

**触发时机**：所有 task 完成、测试通过后。

**做什么**：
1. 验证全量测试通过
2. 提供 4 个选项：
   - 本地合并到主分支
   - 创建 PR
   - 保留分支
   - 丢弃工作

## 5. 实战案例：Airway MCP Server

本分支就是用 superpowers 插件完成的。以下是实际产出物：

### 5.1 Spec 产出

```
docs/superpowers/specs/2026-06-05-airway-mcp-server-design.md
```

内容包括：
- 背景与目标（集成 Bisheng RAG + Clawith Agent）
- 架构方案（独立 MCP 服务、共享基础设施）
- 3 个核心模块（Auth Proxy、MCP Tools、Bisheng Client）
- 技术选型（7 个直接依赖）
- 配置项、部署方式、错误处理

### 5.2 Plan 产出

```
docs/superpowers/plans/2026-06-05-airway-mcp-server.md
```

将 spec 拆解为 9 个 task：

| Task | 内容 | 产出文件 |
|------|------|----------|
| 1 | 项目脚手架 | `pyproject.toml`, 目录结构, `conftest.py` |
| 2 | Config 模块 | `config.py`, `test_config.py` |
| 3 | User Mapping 模型 | `mapping.py`, `test_models.py` |
| 4 | Bisheng Client 认证 | `bisheng.py`（认证部分）, `test_client.py` |
| 5 | Bisheng Client 知识库 | `bisheng.py`（API 部分）, `test_client.py` |
| 6 | Auth Proxy | `proxy.py`, `test_auth.py` |
| 7 | MCP Tools | `tools.py`, `test_tools.py` |
| 8 | MCP Server 入口 | `server.py` |
| 9 | .gitignore 更新 | `.gitignore` |

每个 task 都遵循 TDD 流程：
1. 写测试 → 确认失败
2. 写实现 → 确认通过
3. 提交

### 5.3 实际提交记录

```
c30902b feat: Bisheng client knowledge list/detail/search APIs
ffc5549 feat: AirwayTools with knowledge list/detail/search
4ea73f8 feat: AuthProxy with Redis caching and auto-register
1e84777 feat: MCP Server entry point with stdio and streamable-http
7d0de89 chore: update gitignore for Airway project
```

## 6. 常见问题

### Q: 可以跳过 brainstorming 直接写代码吗？

不可以。brainstorming 是硬门禁。但你可以通过明确的需求描述加快这个过程——需求越清晰，brainstorming 越快完成。

### Q: task 之间有依赖怎么办？

用 `executing-plans` 顺序执行，不用 `subagent-driven-development`。在 plan 中明确标注 task 之间的依赖关系。

### Q: TDD 太慢了，可以后补测试吗？

superpowers 强制 TDD。先写测试的好处是：
1. 强制你先思考接口设计
2. 测试即文档
3. 重构时有安全网

### Q: 代码审查不通过怎么办？

修复审查指出的问题，然后重新运行审查。Critical 级别的问题会阻塞后续 task。

### Q: 如果 spec 或 plan 需要调整？

直接修改 `docs/superpowers/` 下的文档，然后重新确认。不要口头传达变更——所有设计决策必须有文档记录。

### Q: 可以只用部分 skill 吗？

可以。但推荐至少使用 brainstorming → writing-plans → TDD 这三个核心 skill。跳过任何一个都会降低开发质量。
