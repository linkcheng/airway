import httpx
import json
import pytest
import respx

from airway.bisheng_client import BishengAPIClient, BishengAPIError
from airway.rag_tools import workflow_list, workflow_run, workflow_run_once
from airway.settings import Settings


@pytest.fixture
def client() -> BishengAPIClient:
    settings = Settings(
        bisheng_api_url="http://bisheng-test:7860",
        bisheng_token="test-token",
        api_timeout=5.0,
    )
    return BishengAPIClient(settings)


BISHENG_URL = "http://bisheng-test:7860"


@pytest.mark.asyncio
async def test_workflow_list(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.get(f"{BISHENG_URL}/api/v1/workflow/list").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "w1", "name": "报告生成", "description": "生成分析报告", "status": 2, "flow_type": 10},
                        {"id": "w2", "name": "数据清洗", "description": "ETL流程", "status": 2, "flow_type": 10},
                    ]
                },
            )
        )
        result = await workflow_list(client)
        assert len(result) == 2
        assert result[0]["id"] == "w1"
        assert result[0]["name"] == "报告生成"
        assert result[1]["flow_type"] == 10


@pytest.mark.asyncio
async def test_workflow_list_with_keyword(client: BishengAPIClient) -> None:
    with respx.mock:
        route = respx.get(f"{BISHENG_URL}/api/v1/workflow/list").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "w1", "name": "报告生成", "description": "", "status": 2, "flow_type": 10}]},
            )
        )
        result = await workflow_list(client, keyword="报告")
        assert len(result) == 1
        assert "name=" in str(route.calls[0].request.url)


@pytest.mark.asyncio
async def test_workflow_run(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.post(f"{BISHENG_URL}/api/v2/workflow/invoke").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_id": "sess-123",
                    "events": [
                        {
                            "node_name": "LLM节点",
                            "output_schema": {"message": "分析结果：一切正常"},
                        },
                        {
                            "node_name": "输出节点",
                            "output_schema": {"message": "报告已生成"},
                        },
                    ],
                },
            )
        )
        result = await workflow_run(client, workflow_id="w1", input={"query": "测试"})
        assert result["session_id"] == "sess-123"
        assert len(result["outputs"]) == 2
        assert result["outputs"][0]["message"] == "分析结果：一切正常"


@pytest.mark.asyncio
async def test_workflow_run_with_session(client: BishengAPIClient) -> None:
    with respx.mock:
        route = respx.post(f"{BISHENG_URL}/api/v2/workflow/invoke").mock(
            return_value=httpx.Response(
                200,
                json={"session_id": "sess-456", "events": []},
            )
        )
        result = await workflow_run(client, workflow_id="w1", session_id="sess-123")
        assert result["session_id"] == "sess-456"
        body = route.calls[0].request.read()
        parsed = json.loads(body)
        assert parsed["session_id"] == "sess-123"
        assert parsed["stream"] is False


@pytest.mark.asyncio
async def test_workflow_run_once(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.post(f"{BISHENG_URL}/api/v1/workflow/run_once").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"key": "result", "value": "节点输出", "type": "output"},
                        {"key": "score", "value": 0.95, "type": "variable"},
                    ]
                },
            )
        )
        result = await workflow_run_once(
            client, workflow_id="w1", node_input={"text": "输入"}
        )
        assert len(result) == 2
        assert result[0]["key"] == "result"
        assert result[0]["value"] == "节点输出"
        assert result[1]["value"] == 0.95


@pytest.mark.asyncio
async def test_workflow_run_once_error(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.post(f"{BISHENG_URL}/api/v1/workflow/run_once").mock(
            return_value=httpx.Response(500, text="Workflow execution failed")
        )
        with pytest.raises(BishengAPIError) as exc_info:
            await workflow_run_once(client, workflow_id="w1")
        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_workflow_list_empty(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.get(f"{BISHENG_URL}/api/v1/workflow/list").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        result = await workflow_list(client)
        assert result == []
