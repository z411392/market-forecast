from math import inf, log, nan

from pytest import approx, mark, raises

from libs.realized_variance.domain.services.calculate_overnight_log_return import (
    calculate_overnight_log_return,
)
from libs.realized_variance.exceptions.invalid_realized_variance_input_error import (
    InvalidRealizedVarianceInputError,
)


@mark.unit
def test_calculate_overnight_log_return() -> None:
    assert calculate_overnight_log_return(100.0, 110.0) == approx(log(1.1))
    assert calculate_overnight_log_return(100.0, 90.0) == approx(log(0.9))

    for invalid_previous, invalid_current in (
        (0.0, 100.0),
        (-1.0, 100.0),
        (100.0, 0.0),
        (100.0, -1.0),
        (nan, 100.0),
        (100.0, nan),
        (inf, 100.0),
        (100.0, inf),
    ):
        with raises(InvalidRealizedVarianceInputError):
            calculate_overnight_log_return(invalid_previous, invalid_current)
