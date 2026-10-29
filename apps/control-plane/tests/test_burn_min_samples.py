from typing import Any

import pytest
from reflex_cp.sentinel.burn import BurnEvaluator


class _Agg:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def to_list(self, _n: Any) -> list[dict[str, Any]]:
        return self.rows


class _Slos:
    def find(self, *_a: Any, **_k: Any) -> Any:
        async def gen() -> Any:
            yield {
                "_id": "route:r:quality",
                "scope": "route",
                "key": "r",
                "sli": "quality",
                "objective": 0.995,
            }

        return gen()


class _Sli:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row

    async def aggregate(self, _pipeline: Any) -> _Agg:
        return _Agg([{"key": "r", **self.row}])


def _db(short: tuple[int, int], long: tuple[int, int]) -> dict[str, Any]:
    (gs, ts), (gl, tl) = short, long
    row = {"q_good_short": gs, "q_elig_short": ts, "q_good_long": gl, "q_elig_long": tl}
    return {"slos": _Slos(), "sli_1m": _Sli(row)}


@pytest.mark.asyncio
async def test_single_bad_request_on_quiet_route_does_not_fire() -> None:
    # 1 lỗi / 4 request (short), 1 / 12 (long): burn rất cao nhưng quá ít mẫu
    [ev] = await BurnEvaluator(_db((3, 4), (11, 12))).evaluate()  # type: ignore[arg-type]
    assert ev["burn_short"] > 14.4 and ev["burn_long"] > 14.4
    assert ev["fires"] is False


@pytest.mark.asyncio
async def test_sustained_degradation_with_enough_samples_fires() -> None:
    [ev] = await BurnEvaluator(_db((6, 10), (60, 100))).evaluate()  # type: ignore[arg-type]
    assert ev["fires"] is True
