import json
import multiprocessing as mp
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

import modal

APP_NAME = "primary-compute"
CPU_CORES = float(os.getenv("PRIMARY_MODAL_CPU", "6"))
MEMORY_MB = int(os.getenv("PRIMARY_MODAL_MEMORY_MB", str(14 * 1024)))
TIMEOUT_SECONDS = int(os.getenv("PRIMARY_MODAL_TIMEOUT_SECONDS", str(2 * 60 * 60)))
MAX_MIN_PER_DAY = float(os.getenv("PRIMARY_MODAL_MAX_MIN_PER_DAY", str(3 * 60)))
STATE_PATH = Path(
    os.getenv(
        "PRIMARY_MODAL_USAGE_FILE",
        str(Path.home() / ".primary_compute_modal_usage.json"),
    )
)

app = modal.App(APP_NAME)

if hasattr(modal, "Resources"):
    FUNCTION_RESOURCES = {"resources": modal.Resources(cpu=CPU_CORES, memory=MEMORY_MB)}
else:
    FUNCTION_RESOURCES = {"cpu": CPU_CORES, "memory": MEMORY_MB}


def _worker_checksum(args: tuple[int, int, int]) -> int:
    start, count, salt = args
    acc = 0
    end = start + count
    for i in range(start, end):
        acc = (acc + ((i * i + salt) ^ (i * 2654435761))) & 0xFFFFFFFFFFFFFFFF
    return acc


def do_heavy_stuff(payload: dict[str, Any]) -> dict[str, Any]:
    iterations = int(payload.get("iterations", 24_000_000))
    workers = int(payload.get("workers", min(6, os.cpu_count() or 1)))
    workers = max(1, workers)
    salt = int(payload.get("salt", 17))

    base = iterations // workers
    rem = iterations % workers
    ranges: list[tuple[int, int, int]] = []
    offset = 0
    for idx in range(workers):
        chunk = base + (1 if idx < rem else 0)
        ranges.append((offset, chunk, salt))
        offset += chunk

    started = time.time()
    if workers == 1:
        parts = [_worker_checksum(ranges[0])]
    else:
        with mp.Pool(processes=workers) as pool:
            parts = pool.map(_worker_checksum, ranges)
    duration_s = time.time() - started

    checksum = 0
    for value in parts:
        checksum ^= value

    return {
        "iterations": iterations,
        "workers": workers,
        "checksum": checksum,
        "duration_s": round(duration_s, 3),
        "host": os.uname().sysname if hasattr(os, "uname") else os.name,
    }


@app.function(timeout=TIMEOUT_SECONDS, **FUNCTION_RESOURCES)
def heavy_task(payload: dict[str, Any]) -> dict[str, Any]:
    result = do_heavy_stuff(payload)
    result["execution"] = "modal"
    result["modal_cpu"] = CPU_CORES
    result["modal_memory_mb"] = MEMORY_MB
    return result


def _read_state() -> dict[str, Any]:
    today = date.today().isoformat()
    if not STATE_PATH.exists():
        return {"day": today, "used_min": 0.0}

    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"day": today, "used_min": 0.0}

    if data.get("day") != today:
        return {"day": today, "used_min": 0.0}
    return {"day": today, "used_min": float(data.get("used_min", 0.0))}


def _write_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def should_use_modal(max_min_per_day: float = MAX_MIN_PER_DAY) -> tuple[bool, dict[str, Any]]:
    state = _read_state()
    return state["used_min"] < max_min_per_day, state


def _run_locally(payload: dict[str, Any]) -> dict[str, Any]:
    result = do_heavy_stuff(payload)
    result["execution"] = "local"
    return result


def run_heavy(
    payload: dict[str, Any],
    max_min_per_day: float = MAX_MIN_PER_DAY,
    allow_local_fallback: bool = False,
    force_mode: str = "auto",
) -> dict[str, Any]:
    mode = force_mode.lower().strip()
    if mode not in {"auto", "modal", "local"}:
        raise ValueError("mode must be one of: auto, modal, local")

    if mode == "local":
        return _run_locally(payload)

    if mode == "modal":
        start = time.time()
        result = heavy_task.remote(payload)
        elapsed_min = (time.time() - start) / 60.0
        state = _read_state()
        state["used_min"] += elapsed_min
        _write_state(state)
        result["tracked_modal_min_today"] = round(state["used_min"], 3)
        return result

    use_modal, state = should_use_modal(max_min_per_day=max_min_per_day)
    if use_modal:
        start = time.time()
        result = heavy_task.remote(payload)
        elapsed_min = (time.time() - start) / 60.0
        state["used_min"] += elapsed_min
        _write_state(state)
        result["tracked_modal_min_today"] = round(state["used_min"], 3)
        result["daily_budget_min"] = max_min_per_day
        return result

    if allow_local_fallback:
        result = _run_locally(payload)
        result["tracked_modal_min_today"] = round(state["used_min"], 3)
        result["daily_budget_min"] = max_min_per_day
        return result

    raise RuntimeError(
        "Modal daily budget reached. Re-run with --allow-local-fallback=1 "
        "or --mode=modal to force remote."
    )


@app.local_entrypoint()
def main(
    payload: str = "{}",
    mode: str = "auto",
    max_min_per_day: float = MAX_MIN_PER_DAY,
    allow_local_fallback: int = 0,
    show_state: int = 0,
):
    if show_state:
        print(json.dumps(_read_state(), indent=2))
        return

    payload_obj = json.loads(payload)
    result = run_heavy(
        payload_obj,
        max_min_per_day=max_min_per_day,
        allow_local_fallback=bool(allow_local_fallback),
        force_mode=mode,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
