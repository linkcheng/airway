# Tasks: workflow-bridge

## 1. workflow_list 工具函数
- [ ] 在 `rag_tools.py` 添加 `workflow_list()` 函数
- [ ] 调用 `GET /api/v1/workflow/list`，传递 keyword/page_size/page_num 参数
- [ ] 精简返回字段：id, name, description, status, flow_type

## 2. workflow_run 工具函数
- [ ] 在 `rag_tools.py` 添加 `workflow_run()` 函数
- [ ] 调用 `POST /api/v2/workflow/invoke`，`stream=false`
- [ ] 参数：workflow_id, input, session_id
- [ ] 精简返回：session_id, outputs

## 3. workflow_run_once 工具函数
- [ ] 在 `rag_tools.py` 添加 `workflow_run_once()` 函数
- [ ] 调用 `POST /api/v1/workflow/run_once`
- [ ] 参数：workflow_id, node_input, node_data
- [ ] 精简返回：outputs

## 4. MCP Tool 注册
- [ ] 在 `app.py` 注册 3 个新 Tool：workflow_list_tool, workflow_run_tool, workflow_run_once_tool
- [ ] 更新 import

## 5. 测试
- [ ] 创建 `tests/test_workflow_tools.py`
- [ ] 测试 workflow_list 返回精简列表
- [ ] 测试 workflow_run 返回 session_id + outputs
- [ ] 测试 workflow_run_once 返回 outputs
- [ ] 测试错误场景（404、500）
