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
    for index in range(50):
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

    # xW requires both RV5 and RV22.  RV22 remains unavailable through
    # index 41 because every 22-session window through that origin still
    # contains the explicit missing measurement at index 20.
    assert np.all(np.isnan(h5.x_w[20:42]))
    assert np.isfinite(h5.x_w[42])

    assert np.all(np.isnan(h5.rv22[20:42]))
    assert np.isfinite(h5.rv22[42])

    # H=5 origins 15..19 have future windows crossing index 20.
    assert np.all(np.isnan(h5.target[15:20]))
    assert np.isfinite(h5.target[20])

    # H=20 origins 0..19 cross index 20; origin 20 starts at session 21.
    assert np.all(np.isnan(h20.target[0:20]))
    assert np.isfinite(h20.target[20])
