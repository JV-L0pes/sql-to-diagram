import re
import tomllib
from pathlib import Path

API_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
REQUIREMENTS = Path(__file__).resolve().parents[3] / "api" / "requirements.txt"

_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _dependency_names(entries: list[str]) -> set[str]:
    names = set()
    for entry in entries:
        stripped = entry.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _NAME_RE.match(stripped)
        if match:
            names.add(match.group(1).lower().replace("_", "-"))
    return names


def _pyproject_runtime_dependencies() -> set[str]:
    content = tomllib.loads(API_PYPROJECT.read_text(encoding="utf-8"))
    return _dependency_names(content["project"]["dependencies"])


def _requirements_dependencies() -> set[str]:
    return _dependency_names(REQUIREMENTS.read_text(encoding="utf-8").splitlines())


def test_deploy_manifest_lists_every_runtime_dependency() -> None:
    """Vercel installs api/requirements.txt only; it must not miss a runtime dep."""
    missing = _pyproject_runtime_dependencies() - _requirements_dependencies()
    assert missing == set(), (
        f"api/requirements.txt is missing runtime dependencies: {sorted(missing)}"
    )
