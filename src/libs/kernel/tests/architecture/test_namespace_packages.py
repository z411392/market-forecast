from importlib.util import find_spec

from pytest import mark


@mark.architecture
def test_namespace_packages_work_without_init() -> None:
    assert find_spec("libs") is not None
    assert find_spec("libs.kernel") is not None
