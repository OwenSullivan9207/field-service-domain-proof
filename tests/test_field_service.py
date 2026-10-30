import json

from src.field_service import FieldServiceOnboarding, InfraiClient


class Response:
    status = 200
    headers = {}

    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()


def test_verification_gate_loads_user_only_after_domain_proof():
    calls = []
    responses = iter([
        {"ok": True, "data": {"record_id": "r1"}, "error": None, "metadata": {}},
        {"ok": True, "data": {"verified": True}, "error": None, "metadata": {}},
        {"ok": True, "data": {"id": "u1", "email": "tech@example.com"}, "error": None, "metadata": {}},
    ])

    def opener(request):
        calls.append((request.method, request.full_url, request.headers["Authorization"]))
        return Response(next(responses))

    client = InfraiClient("test-key", opener=opener)
    result = FieldServiceOnboarding(client).prove_domain_and_load_user(
        "example.com", "tech@example.com", "zone-1", "verify-me"
    )

    assert result == {"onboarded": True, "domain": "example.com", "user": {"id": "u1", "email": "tech@example.com"}}
    assert [item[0] for item in calls] == ["PUT", "POST", "GET"]
    assert calls[-1][2] == "Bearer test-key"
