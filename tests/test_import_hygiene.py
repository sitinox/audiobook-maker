import ast
from pathlib import Path


def test_package_uses_no_wildcard_imports() -> None:
    package_dir = Path(__file__).parents[1] / "audiobook_maker"
    offenders: list[str] = []

    for module_path in sorted(package_dir.glob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                offenders.append(module_path.name)

    assert offenders == [], f"Wildcard imports found in: {', '.join(offenders)}"
