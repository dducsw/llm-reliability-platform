from datetime import UTC, datetime

from reflex_core.incident import Signal, TimelineEntry
from reflex_mongo.serde import to_doc

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def test_to_doc_keeps_datetime_and_flattens_enums() -> None:
    entry = to_doc(TimelineEntry(at=NOW, kind="status_change", actor="verifier"))
    assert entry["at"] == NOW and isinstance(entry["at"], datetime)


def test_to_doc_nested_signal_keeps_datetime() -> None:
    sig = to_doc(Signal(source="sentinel", at=NOW))
    assert isinstance(sig["at"], datetime)
    assert type(sig["source"]) is str
