from ast import Import, ImportFrom, parse, walk
from pathlib import Path

from pytest import mark

_SRC = Path(__file__).resolve().parents[4]
_INTER_FEATURE_SURFACE = {"ports", "dtos"}
_APP_PUBLIC_SURFACE = {"ports", "dtos", "exceptions"}
_FORBIDDEN_FILENAMES = {
    "__init__.py",
    "common.py",
    "composition.py",
    "errors.py",
    "misc.py",
    "ports.py",
    "service.py",
    "utils.py",
}
_FORBIDDEN_DIRECTORY_NAMES = {"contracts", "public", "shared", "types"}
_FORBIDDEN_APP_LAYERS = {"application", "domain", "ports"}


@mark.architecture
def test_repository_architecture() -> None:
    files = sorted(_SRC.rglob("*.py"))
    module_imports = [_module_imports(path) for path in files]

    path_violations = _path_violations(files)
    import_violations = [
        f"{module} imports {imported}: {reason}"
        for module, imports in module_imports
        for imported in imports
        if (reason := _import_violation(module, imported)) is not None
    ]
    dependency_edges = {
        edge
        for module, imports in module_imports
        for imported in imports
        if (edge := _feature_dependency_edge(module, imported)) is not None
    }
    dependency_cycle = _dependency_cycle(dependency_edges)

    assert path_violations == []
    assert import_violations == []
    assert dependency_cycle is None, "feature dependency cycle: " + " -> ".join(dependency_cycle or [])

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
        (
            "apps.cli.entrypoints",
            "libs.realized_variance.application.commands.build_realized_variance",
        ),
        (
            "libs.risk_forecast.application.commands.fit_model",
            "libs.realized_variance.exceptions.measurement_error",
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
            "apps.cli.adapters.driving.measure",
            "libs.realized_variance.exceptions.measurement_error",
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

    assert _dependency_cycle(
        {
            ("risk_forecast", "realized_variance"),
            ("realized_variance", "market_data"),
        }
    ) is None
    assert _dependency_cycle(
        {
            ("market_data", "realized_variance"),
            ("realized_variance", "market_data"),
        }
    ) == ["market_data", "realized_variance", "market_data"]


def _path_violations(files: list[Path]) -> list[str]:
    violations: list[str] = []

    for path in files:
        relative = path.relative_to(_SRC)

        if path.name in _FORBIDDEN_FILENAMES:
            violations.append(f"forbidden filename: {relative}")

        parts = set(relative.parts)
        forbidden_dirs = sorted(parts & _FORBIDDEN_DIRECTORY_NAMES)
        for directory in forbidden_dirs:
            violations.append(f"forbidden directory '{directory}': {relative}")

        if relative.parts[0] == "apps":
            forbidden_app_layers = sorted(parts & _FORBIDDEN_APP_LAYERS)
            for layer in forbidden_app_layers:
                violations.append(f"app owns forbidden layer '{layer}': {relative}")

            if "adapters" in relative.parts:
                adapter_index = relative.parts.index("adapters")
                if len(relative.parts) > adapter_index + 1 and relative.parts[adapter_index + 1] == "driven":
                    violations.append(f"app owns driven adapter: {relative}")

    return violations


def _module_imports(path: Path) -> tuple[str, list[str]]:
    module = ".".join(path.relative_to(_SRC).with_suffix("").parts)
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
        if layer not in _INTER_FEATURE_SURFACE:
            return "a feature may only depend on another feature through ports/dtos"
        return None

    if importer_root == "apps" and imported_root == "libs":
        if importer.endswith(".module"):
            return None

        layer = imported_parts[2] if len(imported_parts) > 2 else ""
        if layer not in _APP_PUBLIC_SURFACE:
            return "app code outside the composition root must depend on a feature public contract"
        return None

    return None


def _feature_dependency_edge(importer: str, imported: str) -> tuple[str, str] | None:
    importer_parts = importer.split(".")
    imported_parts = imported.split(".")

    if "tests" in importer_parts:
        return None
    if len(importer_parts) < 2 or len(imported_parts) < 2:
        return None
    if importer_parts[0] != "libs" or imported_parts[0] != "libs":
        return None

    source = importer_parts[1]
    target = imported_parts[1]
    if source == target or source == "kernel" or target == "kernel":
        return None
    return source, target


def _dependency_cycle(edges: set[tuple[str, str]]) -> list[str] | None:
    graph: dict[str, set[str]] = {}
    for source, target in edges:
        graph.setdefault(source, set()).add(target)
        graph.setdefault(target, set())

    visited: set[str] = set()
    active: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in active:
            start = stack.index(node)
            return [*stack[start:], node]
        if node in visited:
            return None

        active.add(node)
        stack.append(node)
        for target in sorted(graph[node]):
            if cycle := visit(target):
                return cycle
        stack.pop()
        active.remove(node)
        visited.add(node)
        return None

    for node in sorted(graph):
        if cycle := visit(node):
            return cycle
    return None
