"""Unit test bench importer (không cần Mongo).

Fixture nhỏ: vài dòng JSONL mô phỏng data/YYYY-MM/*.jsonl của Jwrede/llm-bench-data.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from reflex_sim.bench.importer import date_range, normalize, to_docs


def _line(
    model: str = "anthropic/claude-sonnet-4.6",
    ts: str = "2026-10-18T14:00:00Z",
    status: str = "healthy",
    *,
    latency: float = 2100,
) -> str:
    return json.dumps(
        {
            "provider": "openai",
            "model": model,
            "status": status,
            "ttft_ms": 312.5,
            "latency_ms": latency,
            "tokens_per_sec": 68.4,
            "token_count": 20,
            "timestamp": ts,
        }
    )


class TestNormalize:
    def test_valid_row(self) -> None:
        doc = normalize(_line())
        assert doc is not None
        assert doc["ts"] == datetime(2026, 10, 18, 14, tzinfo=UTC)
        assert doc["meta"]["model"] == "anthropic/claude-sonnet-4.6"
        assert doc["meta"]["vendor"] == "anthropic"
        assert doc["meta"]["source"] == "llm-bench-data"
        assert doc["meta"]["route_proto"] == "openai"
        assert doc["status"] == "healthy"
        assert doc["ttft_ms"] == 312.5
        assert doc["latency_ms"] == 2100
        assert doc["tps"] == 68.4
        assert doc["token_count"] == 20

    def test_malformed_rows_dropped(self) -> None:
        assert normalize("not json") is None
        assert normalize('{"model": "openai/gpt-5.5"}') is None  # thiếu timestamp
        assert normalize('{"timestamp": "2026-10-18T14:00:00Z", "model": "their"}') is None
        assert normalize(_line(ts="18/10/2026")) is None  # sai ISO

    def test_ts_normal(self) -> None:
        assert normalize(_line(ts="2026-10-18T14:00:00+07:00")) is not None


class TestToDocs:
    def test_dedup_by_model_ts(self) -> None:
        docs = to_docs([_line(), _line(), _line(model="openai/gpt-5.5")])
        assert len(docs) == 2
        assert {d["meta"]["model"] for d in docs} == {
            "anthropic/claude-sonnet-4.6",
            "openai/gpt-5.5",
        }

    def test_sorted_by_model_then_ts(self) -> None:
        docs = to_docs(
            [
                _line(model="openai/gpt-5.5", ts="2026-10-18T13:00:00Z"),
                _line(ts="2026-10-18T15:00:00Z"),
                _line(ts="2026-10-18T14:00:00Z"),
            ]
        )
        keys = [(d["meta"]["model"], d["ts"]) for d in docs]
        assert keys == sorted(keys)

    def test_batch_from_fixture_file(self, tmp_path: Path) -> None:
        fixture = tmp_path / "2026-10-18.jsonl"
        fixture.write_text("\n".join([_line(), _line(), "", "junk"]), encoding="utf-8")
        docs = to_docs(iter(fixture.read_text(encoding="utf-8").splitlines()))
        assert len(docs) == 1  # 2 dòng trùng nhau (dedup còn 1), 1 dòng trống, 1 dòng rác


class TestDateRange:
    def test_excludes_today(self) -> None:
        now = datetime(2026, 10, 21, 15, 30, tzinfo=UTC)
        days = list(date_range(3, until=now))
        assert days == [
            datetime(2026, 10, 18, tzinfo=UTC),
            datetime(2026, 10, 19, tzinfo=UTC),
            datetime(2026, 10, 20, tzinfo=UTC),
        ]
