"""reflex-core — domain thuần, dùng chung bởi gateway, control-plane, cortex và Time Machine.

Quy tắc: không I/O. Clock và RNG luôn được inject (xem `Clock`, `Rng` trong `ids.py`)
để Time Machine replay đúng hành vi thật.
"""

SCHEMA_VERSION = 1
