import importlib.util
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from pytest import mark

_RUNNER_PATH = (
    Path(__file__).parents[5]
    / "docs"
    / "research"
    / "experiments"
    / "run_task_101_canonical_transferability.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "task_101_canonical_transferability_runner",
    _RUNNER_PATH,
)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("task101_test_runner_import_spec_missing")
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
_build_panel = _MODULE._build_panel


@mark.unit
def test_task_101_missing_measurement_breaks_local_session_windows() -> None:
    start = date(2024, 1, 2)
    rows = []
    for index in range(40):
        rows.append(
            {
                "session_date": (start + timedelta(days=index)).isoformat(),
                "whole_day_variance": 0.01 + index * 0.0001,
            }
        )

    rows[20]["whole_day_variance"] = None
    entry = {
        "market": "us",
        "rows": rows,
    }

    h5 = _build_panel(entry, 5)
    h20 = _build_panel(entry, 20)

    assert math.isnan(h5.rv[20])

    assert np.all(np.isnan(h5.x_w[20:25]))
    assert np.isfinite(h5.x_w[25])

    assert np.all(np.isnan(h5.rv22[20:40]))

    assert np.all(np.isnan(h5.target[15:21]))
    assert np.all(np.isnan(h20.target[0:21]))
