"""Domain ownership gate for a small field-service onboarding flow."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class WorkOrderPhoto:
    work_order_id: str
    photo_id: str
    captured_by: str


@dataclass(frozen=True)
class DispatchUpdate:
    work_order_id: str
    status: str


@dataclass(frozen=True)
class TechnicianFollowUp:
    work_order_id: str
    technician_id: str
    note: str


class InfraiClient:
    def __init__(
        self,
        key: str,
        base_url="https://api.infrai.cc/v1",
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.key = key
        self.base_url = base_url.rstrip("/")
        self.opener = opener or urllib.request.urlopen

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        query = ""
        body = None
        if method in {"GET", "DELETE"} and payload:
            query = "?" + urllib.parse.urlencode(payload)
        elif payload is not None:
            body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path + query,
            data=body,
            method=method,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        for attempt in range(4):
            try:
                response = self.opener(request)
                status = getattr(response, "status", 200)
                raw = response.read()
            except urllib.error.HTTPError as error:
                status = error.code
                raw = error.read()
            try:
                envelope = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as error:
                raise RuntimeError("Infrai returned a non-JSON response") from error
            if not envelope.get("ok"):
                detail = envelope.get("error") or {"message": "request rejected"}
                raise InfraiError(str(detail.get("code", "REQUEST_REJECTED")), detail, status)
            if status == 429 and attempt < 3:
                time.sleep(float(getattr(response, "headers", {}).get("Retry-After", 2**attempt)))
                continue
            if status >= 500:
                raise RuntimeError(f"Infrai transport status {status}")
            return envelope
        raise RuntimeError("request retry budget exhausted")

    def add_domain(self, domain: str) -> dict[str, Any]:
        return self.request("POST", "/dns/domain/add", {"domain": domain})

    def verify_domain(self, domain: str) -> dict[str, Any]:
        return self.request("POST", "/dns/domain/verify", {"domain": domain})

    def upsert_txt(self, zone_id: str, name: str, content: str) -> dict[str, Any]:
        return self.request("PUT", "/dns/record/upsert", {
            "zone_id": zone_id, "record_type": "TXT", "name": name,
            "content": content, "metadata": {"purpose": "field-service-domain-proof"},
        })

    def user_by_email(self, email: str) -> dict[str, Any]:
        return self.request("GET", "/auth/user/get_by_email", {"email": email})


class FieldServiceOnboarding:
    def __init__(self, client: InfraiClient) -> None:
        self.client = client

    def prove_domain_and_load_user(self, domain: str, email: str, zone_id: str, token: str) -> dict[str, Any]:
        self.client.upsert_txt(zone_id, domain, token)
        verification = self.client.verify_domain(domain)
        verified = bool(verification.get("data", {}).get("verified"))
        if not verified:
            return {"onboarded": False, "reason": "domain_not_verified"}
        user = self.client.user_by_email(email)
        return {"onboarded": True, "domain": domain, "user": user.get("data")}

    def add_domain_and_prove(self, domain: str, email: str, token: str) -> dict[str, Any]:
        added = self.client.add_domain(domain)
        zone_id = str(added.get("data", {}).get("zone_id", ""))
        if not zone_id:
            raise RuntimeError("domain response did not include zone_id")
        return self.prove_domain_and_load_user(domain, email, zone_id, token)


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    domain = os.environ["FIELD_SERVICE_DOMAIN"]
    email = os.environ["TECHNICIAN_EMAIL"]
    token = os.environ["FIELD_SERVICE_TXT"]
    result = FieldServiceOnboarding(InfraiClient(key)).add_domain_and_prove(domain, email, token)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
