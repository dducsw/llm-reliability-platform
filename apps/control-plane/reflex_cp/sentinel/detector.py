"""Multi-window rule → mở incident (source: sentinel). A6 anomaly, A7 probe blindness."""

from __future__ import annotations


class Detector:
    async def detect(self, evaluations: list[dict]) -> None:
        raise NotImplementedError
