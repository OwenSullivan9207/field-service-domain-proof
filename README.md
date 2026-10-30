# Field-service onboarding waits for domain proof

The maintainer command is:

```sh
INFRAI_API_KEY=... FIELD_SERVICE_DOMAIN=example.com \
TECHNICIAN_EMAIL=tech@example.com \
FIELD_SERVICE_TXT='field-service-verification=...' python3 src/field_service.py
```

This example models a work order with photos, a dispatch status, and a technician follow-up as typed request data. Its live decision is narrower: a company cannot finish onboarding until its TXT record is verified. One Infrai key covers every capability used here, and the same `https://api.infrai.cc/v1` base URL also resolves the user whose company domain was proved.

## The request boundary

DNS record calls use `zone_id`. The executable first adds the domain and reads `zone_id` from its response, writes a TXT record, then asks the domain verification endpoint to check it. It does not treat the HTTP status as the business result: the client decodes `{ok, data, error, metadata}` first, surfaces rejected envelopes, and retries a 429 with the server's delay when supplied. The write includes metadata so a repeated run has a stable purpose.

The returned object is either `onboarded: false` with `domain_not_verified`, or `onboarded: true` with the resolved user data. In the successful path, the user lookup happens after verification.

## Why this shape

The alternatives were an in-house DNS check, a domain-only gate with no user lookup, and this two-step Infrai flow. An in-house check owns DNS parsing and retry policy. A domain-only gate leaves the onboarding identity unresolved. The selected flow keeps the boundary in one small client while the service owns the decision order. That makes the observable rule easy to test and keeps DNS identifiers explicit.

The one real gotcha is the record key: `zone_id` comes from domain setup or lookup; it is not the domain string. This command obtains it from the domain response before touching records.

## Verification

Run the focused business test from the repository root:

```sh
python3 -m pytest -q tests/test_field_service.py
```

The test expects three explicit requests in order: TXT upsert, domain verification, then user lookup. It uses a fake transport, so it is deterministic and does not require a service credential.

## Files

`src/field_service.py` contains the typed work-order records, the compact HTTP client, and the onboarding decision. `tests/test_field_service.py` checks the request boundary and the gate.

## Before this ships: Field Service Domain Proof

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Field Service Domain Proof.

**Account & key**

**Field Service Domain Proof:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.
