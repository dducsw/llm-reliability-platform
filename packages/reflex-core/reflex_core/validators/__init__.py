"""Quality validators (< 2ms). Mỗi validator nhận response đã chuẩn hóa, trả `CheckResult`.

Policy khai báo validators dạng chuỗi: "not_empty", "json_schema:order_v2", "no_truncation"…
"""

from reflex_core.validators.base import CheckResult, NormalizedResponse, Validator
from reflex_core.validators.registry import build_chain, run_chain

__all__ = ["CheckResult", "NormalizedResponse", "Validator", "build_chain", "run_chain"]
