from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from reflex_cp.api.auth import require_lab_token

router = APIRouter()

SCENARIO_DIR = Path("scenarios")


def available_scenarios(directory: Path = SCENARIO_DIR) -> list[str]:
    return sorted(p.stem for p in directory.glob("*.yaml"))


@router.get("/api/lab/scenarios")
async def list_scenarios() -> dict[str, Any]:
    return {"scenarios": available_scenarios()}


@router.post("/api/lab/scenarios/{name}/run", dependencies=[Depends(require_lab_token)])
async def run_scenario(name: str, fast: bool = True) -> dict[str, Any]:
    # Chỉ nhận tên nằm trong danh sách scenario có sẵn (không truyền path tùy ý vào subprocess).
    if name not in available_scenarios():
        raise HTTPException(status_code=404, detail=f"Unknown scenario {name}")
    cmd = ["reflex-sim", "run", name, *(["--fast"] if fast else [])]
    proc = await asyncio.create_subprocess_exec(*cmd)
    return {"scenario": name, "fast": fast, "pid": proc.pid, "status": "started"}
