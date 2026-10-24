import json
from datetime import UTC, datetime

from reflex_cp.api.stream import decode_token, encode_token, format_event


def test_resume_token_round_trips_and_rejects_garbage() -> None:
    token = {"_data": "8263ABC"}
    assert decode_token(encode_token(token)) == token
    assert decode_token("not-base64!!") is None
    assert decode_token(None) is None


def test_format_event_matches_console_contract() -> None:
    change = {
        "_id": {"_data": "1"},
        "operationType": "update",
        "fullDocument": {
            "_id": "INC-1",
            "status": "mitigating",
            "at": datetime(2026, 10, 22, tzinfo=UTC),
        },
    }
    frame = format_event("incidents", change)
    lines = frame.strip().split("\n")
    assert lines[0].startswith("id: ") and lines[1] == "event: change"
    payload = json.loads(lines[2][len("data: ") :])
    assert payload["topic"] == "incidents" and payload["op"] == "update"
    assert payload["doc"]["at"].startswith("2026-10-22")


def test_delete_event_carries_document_key() -> None:
    frame = format_event(
        "actions", {"_id": {"_data": "2"}, "operationType": "delete", "documentKey": {"_id": "a1"}}
    )
    assert '"doc": {"_id": "a1"}' in frame
