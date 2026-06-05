CHAT_COMPLETION_OK = {
    "choices": [{"message": {"content": "这是测试回答"}}],
}

WORKFLOW_INVOKE_SSE = (
    'data: {{"session_id": "abc123_async_task_id"}}\n\n'
    'data: {{"event": "node_run", "status": "start"}}\n\n'
)

WORKFLOW_STATUS_RUNNING = {"status": "RUNNING"}
WORKFLOW_STATUS_INPUT = {
    "status": "INPUT",
    "input_schema": {
        "input_type": "dialog_input",
        "value": [{"key": "user_input", "type": "text", "value": "", "required": True}],
    },
    "message_id": "11",
    "node_id": "input_cc36c",
}
WORKFLOW_STATUS_SUCCESS = {"status": "SUCCESS", "result": {"output": "done"}}
WORKFLOW_STATUS_FAILED = {"status": "FAILED", "error": "something went wrong"}

KB_LIST = [
    {"id": "kb_prod_001", "name": "产品文档"},
    {"id": "kb_tech_001", "name": "技术规范"},
]
