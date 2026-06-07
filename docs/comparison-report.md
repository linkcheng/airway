# Airway 分支对比测试报告

> 同一需求（Clawith-Bisheng MCP 代理），四种开发方法论的对照实验结果。

## 一、Phase 1: 客观验证

### 1.1 自动化测试结果

| 检查项 | main | superpower | openspec | speckit |
|--------|------|------------|----------|---------|
| `uv sync --extra dev` | Pass | Pass | Pass | Pass |
| `pytest` | **35/35 Pass** | **17/17 Pass** | **12/12 Pass** | **37/37 Pass** |
| `ruff check` | **0 errors** | 5 errors | 5 errors | **0 errors** |

> main 分支初始测试失败（`redis` 未声明依赖），修复后 35/35 pass + ruff 0 errors。

### 1.2 量化数据

| 指标 | main | superpower | openspec | speckit |
|------|------|------------|----------|---------|
| 源码行数 | 275 | 246 | 213 | 436 |
| 测试行数 | 528 | 310 | 188 | 511 |
| 测试用例数 | 35 | 17 | 12 | 37 |
| 测试/代码比 | 1.92 | 1.26 | 0.88 | 1.17 |
| 源码文件数 | 7 | 11 | 6 | 14 |
| 测试文件数 | 5 | 7 | 3 | 5 |
| Git 提交数 | 6 | 16 | 2 | 2 |

## 二、Phase 2: Spec 质量打分

### A1. 完整性（/5）

| 分支 | 依据 | 得分 |
|------|------|------|
| main | 定义 6 个 MCP 工具（含 Workflow），功能范围最广。有迭代路线图但部分功能未实现 | **4** |
| superpower | 仅 3 个工具（knowledge_list/detail/search），功能范围最窄。约束条件清晰 | **3** |
| openspec | 3 个工具 + 健康检查，有 scenario 描述和决策记录（D1-D5），功能适中 | **3** |
| speckit | 4 个工具 + 优先级排序(P1-P4)，有数据模型和接口契约文档，覆盖最均衡 | **4** |

### A2. 精确性（/5）

| 分支 | 依据 | 得分 |
|------|------|------|
| main | 含代码示例和 API 调用细节，但 Workflow 部分描述较模糊 | **4** |
| superpower | TDD 流程中 spec 精确度较高，每个工具有明确的输入输出 | **4** |
| openspec | scenario 驱动，ADDED 格式定义需求，决策记录明确 | **4** |
| speckit | contracts/mcp-tools.md 接口契约 + data-model.md 数据模型，精确度最高 | **5** |

### A3. 结构化（/5）

| 分支 | 依据 | 得分 |
|------|------|------|
| main | 自由格式技术文档，有章节但无模板约束 | **2** |
| superpower | superpowers 插件的 spec→plan 流程，有结构但文档层级少 | **3** |
| openspec | OpenSpec 标准格式（proposal → design → specs/tasks），最规范 | **5** |
| speckit | SpecKit 模板系统（spec → plan → tasks → contracts → data-model），层次最丰富 | **5** |

### A4. 可追溯性（/5）

| 分支 | 依据 | 得分 |
|------|------|------|
| main | 设计文档独立，无任务分解 | **2** |
| superpower | spec → plan 有对应关系，缺少细粒度任务分解 | **3** |
| openspec | proposal → design → specs → tasks 完整链路，每个 spec 有独立目录 | **4** |
| speckit | spec → research → plan → tasks → contracts → checklist 完整链路 | **5** |

### Spec 小计

| 维度 | main | superpower | openspec | speckit |
|------|------|------------|----------|---------|
| 完整性 | 4 | 3 | 3 | 4 |
| 精确性 | 4 | 4 | 4 | 5 |
| 结构化 | 2 | 3 | 5 | 5 |
| 可追溯性 | 2 | 3 | 4 | 5 |
| **小计** | **12/20** | **13/20** | **16/20** | **19/20** |

## 三、Phase 3: 代码质量打分

### B1. 能不能跑

| 分支 | pytest | ruff | 综合 |
|------|--------|------|------|
| main | 35/35 Pass | 0 errors | **Full Pass** |
| superpower | 17/17 Pass | 5 errors | **Partial** |
| openspec | 12/12 Pass | 5 errors | **Partial** |
| speckit | 37/37 Pass | 0 errors | **Full Pass** |

### B2. 模块划分（/5）

| 分支 | 依据 | 得分 |
|------|------|------|
| main | 扁平结构（server.py + config.py + adapters/），简单但职责清晰 | **3** |
| superpower | src/airway 包结构，auth/client/mcp/models 分层，职责明确 | **4** |
| openspec | 最精简（app + client + tools + settings），FastAPI 混合架构合理 | **4** |
| speckit | adapters/protocols 抽象 + models + migrations，最完整但略重 | **4** |

### B3. 代码精简度（/5）

| 分支 | 源码行数 | 功能数 | 效率 | 得分 |
|------|----------|--------|------|------|
| main | 275 | 6 工具 | 45.8 行/工具 | **4** |
| superpower | 246 | 3 工具 | 82.0 行/工具 | **3** |
| openspec | 213 | 3 工具+健康检查 | 53.3 行/功能 | **5** |
| speckit | 436 | 4 工具+健康检查 | 87.2 行/功能 | **3** |

### B4. 可扩展性（/5）

| 分支 | 依据 | 得分 |
|------|------|------|
| main | 硬编码 Bisheng 适配器，新增需要改代码 | **2** |
| superpower | 模块化好，新增工具只需在 mcp/tools.py 注册 | **4** |
| openspec | FastAPI 生命周期管理，工具独立函数，扩展方便 | **4** |
| speckit | abstract protocols.py 接口定义，面向接口编程 | **5** |

### B5. 错误处理（/5）

| 分支 | 依据 | 得分 |
|------|------|------|
| main | AirwayError 自定义异常 + Redis 状态查询，修复后 ruff 0 errors。初始遗漏 redis 依赖，说明 vibe coding 验证不充分 | **3** |
| superpower | try-catch + JSON 错误响应，基本覆盖 | **3** |
| openspec | BishengAPIError + 统一错误格式 + token 自动刷新 | **4** |
| speckit | errors.py 错误转换层 + 输入验证 + structlog 日志，最完善 | **5** |

### 代码小计

| 维度 | main | superpower | openspec | speckit |
|------|------|------------|----------|---------|
| 能跑 | Full Pass | Partial (-1) | Partial (-1) | Full Pass |
| 模块划分 | 3 | 4 | 4 | 4 |
| 代码精简度 | 4 | 3 | 5 | 3 |
| 可扩展性 | 2 | 4 | 4 | 5 |
| 错误处理 | 3 | 3 | 4 | 5 |
| **小计** | **14/20** | **14/20** | **17/20** | **17/20** |

## 四、Phase 4: 方法论效率

### 过程数据

| 指标 | main | superpower | openspec | speckit |
|------|------|------------|----------|---------|
| Git 提交数 | 6 | 16 | 2 | 2 |
| 提交模式 | feat→docs→fix→fix(依赖) | init→docs(5)→feat(6) | init→feat(1次) | init→feat(1次) |
| spec 文档数 | 2 | 3 | 8 | 7 |

### C1. 交互轮次（/5）

| 分支 | 依据 | 得分 |
|------|------|------|
| main | 6 次提交含 2 次 fix（业务逻辑 + 依赖遗漏），有返工 | **2** |
| superpower | 16 次提交，流程最完整但轮次最多 | **2** |
| openspec | 仅 2 次提交（init + 一次性实现），最高效 | **5** |
| speckit | 仅 2 次提交（init + 一次性实现），最高效 | **5** |

### C2. 人工介入（/5）

| 分支 | 依据 | 得分 |
|------|------|------|
| main | 有 2 次 fix 提交（含依赖遗漏修复），人工介入较多 | **2** |
| superpower | 无返工提交，流程驱动下一次性完成 | **4** |
| openspec | 无返工，一次性完成 | **5** |
| speckit | 无返工，一次性完成 | **5** |

### C3. 一次性完成率（/5）

| 分支 | 依据 | 得分 |
|------|------|------|
| main | 修复后 35 pass + ruff 0 errors，但需人工补依赖和修 lint，一次性完成率偏低 | **2** |
| superpower | 全部 pass，但 ruff 5 errors | **3** |
| openspec | 全部 pass，但 ruff 5 errors | **3** |
| speckit | 全部 pass + ruff 0 errors，一次性完成率最高 | **5** |

### C4. 文档产出效率（/5）

| 分支 | 依据 | 得分 |
|------|------|------|
| main | 设计文档详尽但结构松散，无任务分解 | **3** |
| superpower | spec+plan 适度，文档量与代码量比值合理 | **4** |
| openspec | 文档量最大（8个spec文档），对 MVP 阶段略重 | **3** |
| speckit | 文档丰富但质量高（contracts + data-model），投入产出比好 | **3** |

### 方法论效率小计

| 维度 | main | superpower | openspec | speckit |
|------|------|------------|----------|---------|
| 交互轮次 | 2 | 2 | 5 | 5 |
| 人工介入 | 2 | 4 | 5 | 5 |
| 一次性完成率 | 2 | 3 | 3 | 5 |
| 文档产出效率 | 3 | 4 | 3 | 3 |
| **小计** | **9/20** | **13/20** | **16/20** | **18/20** |

## 五、加权总分

| 分支 | Spec (30%) | Code (40%) | Process (30%) | **总分** |
|------|-----------|-----------|--------------|---------|
| main | 12×0.3=3.6 | 14×0.4=5.6 | 9×0.3=2.7 | **11.9/20** |
| superpower | 13×0.3=3.9 | 14×0.4=5.6 | 13×0.3=3.9 | **13.4/20** |
| openspec | 16×0.3=4.8 | 17×0.4=6.8 | 16×0.3=4.8 | **16.4/20** |
| speckit | 19×0.3=5.7 | 17×0.4=6.8 | 18×0.3=5.4 | **17.9/20** |

## 六、结论

### 排名

1. **speckit (17.9)** — 综合最优，spec 质量和工程质量都最高
2. **openspec (16.4)** — 均衡优秀，代码最精简
3. **superpower (13.4)** — 中规中矩，流程完整但产出一般
4. **main (11.9)** — 基准对照，修复后代码可用但过程效率最低

### 各方法定位

| 方法 | 适合场景 | 不适合场景 |
|------|----------|-----------|
| **Vibe Coding** | 快速原型验证、概念探索 | 生产代码、团队协作 |
| **Superpowers** | 个人开发者结构化工作流 | 轻量项目（流程开销大） |
| **OpenSpec** | 变更管理严格的项目、需可审计的需求流程 | 小项目（文档负担重） |
| **SpecKit** | 企业级项目、需要完整规格和验证 | 快速迭代阶段（流程较重） |

### 关键发现

1. **结构化方法 > Vibe Coding**：三种插件方法的综合得分均高于无插件的 vibe coding。main 修复后代码可用，但过程效率最低（需人工补依赖、修 lint）。
2. **spec 质量决定代码质量**：speckit 的 spec 最完整（19/20），其代码质量也最高（37 测试全通过、ruff 零错误）。
3. **vibe coding 的"快"是假象**：main 虽然初始开发快，但后续需要人工修复依赖缺失和 lint 错误，总成本反而更高。
4. **代码精简度冠军是 openspec**：仅 213 行代码实现了完整功能，且测试全通过。
5. **一次性通过率是关键分水岭**：speckit 是唯一初始就 100% 通过（pytest + ruff）的分支。
