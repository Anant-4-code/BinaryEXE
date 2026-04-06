import asyncio
import json
from typing import Any, Dict

from app.schemas.schemas import ExtractionResult
from app.services import gemma_service


class DummyResponse:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Dict[str, Any]:
        return self._payload


class DummyClient:
    def __init__(self, *args: Any, **kwargs: Any):
        pass

    async def __aenter__(self) -> "DummyClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, path: str, json: Dict[str, Any]) -> DummyResponse:
        medicines_json = json.dumps(
            [
                {
                    "medicine": "Amoxicillin",
                    "dose": "500mg",
                    "frequency": "TDS",
                    "duration": "5 days",
                    "instructions": "After meals",
                }
            ]
        )
        return DummyResponse({"response": medicines_json})


def test_call_gemma_parses_valid_json(monkeypatch):
    monkeypatch.setattr(gemma_service, "httpx", type("X", (), {"AsyncClient": DummyClient}))

    result: ExtractionResult = asyncio.run(
        gemma_service.call_gemma("Tab Amox 500mg TDS x 5 days")
    )

    assert result.json_parse_success == 1.0
    assert len(result.medicines) == 1
    med = result.medicines[0]
    assert med.medicine == "Amoxicillin"
    assert med.dose == "500mg"
    assert med.frequency == "TDS"
    assert med.duration == "5 days"
    assert med.instructions == "After meals"

