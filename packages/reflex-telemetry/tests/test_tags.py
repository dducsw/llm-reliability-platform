from reflex_telemetry.datadog_api import strip_chaos_fields
from reflex_telemetry.tags import base_tags


def test_base_tags_only_includes_given_dimensions() -> None:
    assert base_tags("ci") == ["env:ci"]
    assert base_tags("ci", route="order.extract", target="mock:large") == [
        "env:ci",
        "route:order.extract",
        "target:mock:large",
    ]


def test_strip_chaos_fields_removes_nested_keys_and_tags() -> None:
    payload = {
        "attributes": {
            "chaos.fault": "truncate",
            "status": "error",
            "tags": ["chaos.fault:x", "env:ci"],
        },
        "items": [{"chaos_run": "r1", "id": 1}],
    }
    assert strip_chaos_fields(payload) == {
        "attributes": {"status": "error", "tags": ["env:ci"]},
        "items": [{"id": 1}],
    }
