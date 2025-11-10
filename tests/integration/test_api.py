from fastapi.testclient import TestClient

from src.app.api.schemas import AskResponse
from src.app.main import app


def test_post_ask_endpoint(monkeypatch):
    client = TestClient(app)

    stub_payload = {
        "output": "Combined answer",
        "route": "HYBRID",
        "sql_query": "SELECT 1",
        "citations": [
            {
                "source_document": "Contract_Toyota_2023.pdf",
                "page": 4,
                "content": "Warranty details",
            }
        ],
        "tool_trace": ["Router decision: HYBRID"],
    }

    def fake_run_agent(question: str, include_intermediate_steps: bool = True):
        assert question == "Test question"
        return stub_payload

    monkeypatch.setattr("src.app.api.router.run_agent", fake_run_agent)

    response = client.post("/api/v1/ask", json={"question": "Test question"})
    assert response.status_code == 200

    data = AskResponse(**response.json())
    assert data.answer == stub_payload["output"]
    assert data.sql_query == stub_payload["sql_query"]
    assert len(data.citations) == 1
    assert data.tool_trace == stub_payload["tool_trace"]
