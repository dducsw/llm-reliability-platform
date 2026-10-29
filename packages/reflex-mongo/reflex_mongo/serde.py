"""Model → document Mongo: giữ `datetime` là BSON Date (không biến thành chuỗi ISO).

`model_dump(mode="json")` đổi datetime thành chuỗi; `sort`/range query trên trường đó sẽ lẫn kiểu với
dữ liệu seed (BSON xếp Date trước String). Dùng `to_doc` cho mọi thứ ghi vào Mongo.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(v) for v in value]
    return value


def to_doc(model: BaseModel, **kwargs: Any) -> dict[str, Any]:
    """`model_dump` kiểu python (datetime giữ nguyên), enum → value, tuple → list."""
    kwargs.setdefault("by_alias", True)
    return _plain(model.model_dump(mode="python", **kwargs))
