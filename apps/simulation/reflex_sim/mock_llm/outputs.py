"""Re-export: bộ sinh output nằm ở reflex-core để gateway (mock adapter) dùng chung mà không
phải import app `reflex_sim` (import-linter: apps không import lẫn nhau)."""

from reflex_core.mock_outputs import SAMPLE_ORDERS, generate

__all__ = ["SAMPLE_ORDERS", "generate"]
