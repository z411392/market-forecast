from datetime import date, timedelta

import math

import numpy as np
from pytest import mark

from docs.research.experiments.run_task_101_canonical_transferability import (
    _build_panel,
)


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

    # A 5-day trailing mean is unavailable until five complete local-session
    # observations exist again after the explicit missing measurement.
    assert np.all(np.isnan(h5.x_w[20:25]))
    assert np.isfinite(h5.x_w[25])

    # The 22-day denominator remains unavailable for the next 21 local
    # sessions; no row deletion/compression is allowed.
    assert np.all(np.isnan(h5.rv22[20:40]))

    # Future targets that cross the missing local session are unavailable.
    assert np.all(np.isnan(h5.target[15:21]))
    assert np.all(np.isnan(h20.target[0:21]))
