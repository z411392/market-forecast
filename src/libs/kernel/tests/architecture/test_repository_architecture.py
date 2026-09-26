from ast import Import, ImportFrom, parse, walk
from pathlib import Path

SRC = Path(__file__).resolve().parents[4]
PUBLIC_SURFACE = {"ports", "dtos", "constants", "exceptions"}
FORBIDDEN_FILENAMES = {
    "__init__.py",
    "common.py",
    "composition.py",
    "errors.py",
    "misc.py",
    "ports.py",
    "service.py",
    "utils.py",
}
FORBIDDEN_DIRECTORY_NAMES = {"contracts", "public", "shared", "types"}


def test_repository_architecture() -> None:
    files = sorted(SRC.rglob("*.py"))

    path_violations = _path_violations(files)
    import_violations = [
        f"{module} imports {imported}: {reason}"
        for path in files
        for module, imports in [_module_imports(path)]
        for imported in imports
        if (reason := _import_violation(module, imported)) is not None
    ]

    assert path_violations == []
    assert import_violations == []

    forbidden_examples = (
        ("libs.kernel.clock", "libs.market_data.dtos.canonical_minute_bar"),
        ("libs.realized_variance.domain.calculate_rv", "apps.cli.entrypoints"),
        (
            "libs.risk_forecast.application.commands.fit_model",
            "libs.market_data.adapters.driven.massive_adapter",
        ),
        (
            "apps.cli.adapters.driving.measure",
            "libs.realized_variance.application.commands.build_realized_variance",
        ),
    )
    for importer, imported in forbidden_examples:
        assert _import_violation(importer, imported) is not None

    allowed_examples = (
        ("libs.realized_variance.domain.calculate_rv", "libs.kernel.clock"),
        (
            "libs.realized_variance.application.commands.build_realized_variance",
            "libs.market_data.ports.read_minute_bars_port",
        ),
        (
            "libs.risk_forecast.application.commands.fit_model",
            "libs.realized_variance.dtos.realized_variance_observation",
        ),
        (
            "apps.cli.adapters.driving.measure",
            "libs.realized_variance.ports.build_realized_variance_port",
        ),
        (
            "apps.cli.module",
            "libs.market_data.adapters.driven.massive_adapter",
        ),
        (
            "libs.market_data.tests.integration.test_massive_adapter",
            "libs.market_data.adapters.driven.massive_adapter",
        ),
    )
    for importer, imported in allowed_examples:
        assert _import_violation(importer, imported) is None


def _path_violations(files: list[Path]) -> list[str]:
    violations: list[str] = []

    for path in files:
        relative = path.relative_to(SRC)

        if path.name in FORBIDDEN_FILENAMES:
            violations.append(f"forbidden filename: {relative}")

        parts = set(relative.parts)
        forbidden_dirs = sorted(parts & FORBIDDEN_DIRECTORY_NAMES)
        for directory in forbidden_dirs:
            violations.append(f"forbidden directory '{directory}': {relative}")

        if relative.parts[0] == "apps":
            if "ports" in relative.parts:
                violations.append(f"app owns ports: {relative}")
            if "adapters" in relative.parts:
                adapter_index = relative.parts.index("adapters")
                if len(relative.parts) > adapter_index + 1 and relative.parts[adapter_index + 1] == "driven":
                    violations.append(f"app owns driven adapter: {relative}")

    return violations


def _module_imports(path: Path) -> tuple[str, list[str]]:
    module = ".".join(path.relative_to(SRC).with_suffix("").parts)
    tree = parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []

    for node in _walk_imports(tree):
        if isinstance(node, Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ImportFrom):
            if node.level:
                imports.append("<relative-import>")
                continue
            if node.module:
                imports.append(node.module)
                imports.extend(f"{node.module}.{alias.name}" for alias in node.names)

    return module, imports


def _walk_imports(tree: object) -> list[object]:
    return [node for node in walk(tree) if isinstance(node, (Import, ImportFrom))]


def _import_violation(importer: str, imported: str) -> str | None:
    if imported == "<relative-import>":
        return "relative imports are forbidden"

    if not imported.startswith(("libs.", "apps.")):
        return None

    importer_parts = importer.split(".")
    imported_parts = imported.split(".")

    importer_root = importer_parts[0]
    imported_root = imported_parts[0]
    importer_package = importer_parts[1] if len(importer_parts) > 1 else ""
    imported_package = imported_parts[1] if len(imported_parts) > 1 else ""

    importer_is_test = "tests" in importer_parts

    if importer_root == "libs" and imported_root == "apps":
        return "a lib must not depend on an app"

    if importer_is_test:
        return None

    if importer_root == "apps" and imported_root == "apps":
        if importer_package != imported_package:
            return "one app must not depend on another app"
        return None

    if importer_root == "libs" and imported_root == "libs":
        if importer_package == imported_package:
            return None
        if imported_package == "kernel":
            return None
        if importer_package == "kernel":
            return "kernel must not depend on a feature"

        layer = imported_parts[2] if len(imported_parts) > 2 else ""
        if layer not in PUBLIC_SURFACE:
            return (
                "a feature may only depend on another feature through "
                "ports/dtos/constants/exceptions"
            )
        return None

    if importer_root == "apps" and imported_root == "libs":
        if importer.endswith(".module") or importer.endswith(".module.py"):
            return None

        layer = imported_parts[2] if len(imported_parts) > 2 else ""
        is_driving = len(importer_parts) > 4 and importer_parts[2:4] == ["adapters", "driving"]

        if is_driving and layer not in PUBLIC_SURFACE:
            return "a driving adapter must depend on a feature public contract"
        return None

    return None
