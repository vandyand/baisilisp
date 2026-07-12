"""Project configuration discovery for Basilisp command-line tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 only
    import tomli as tomllib  # type: ignore[import-not-found, no-redef]


_COMPILER_OPTIONS = frozenset(
    {
        "generate-auto-inlines",
        "inline-functions",
        "warn-on-arity-mismatch",
        "warn-on-shadowed-name",
        "warn-on-shadowed-var",
        "warn-on-unused-names",
        "warn-on-non-dynamic-set",
        "use-var-indirection",
        "warn-on-var-indirection",
    }
)


class ProjectConfigError(ValueError):
    """Raised when a ``[tool.basilisp]`` table is invalid."""


@dataclass(frozen=True)
class ProjectConfig:
    """The resolved Basilisp configuration from a single ``pyproject.toml`` file."""

    root: Path
    source_paths: tuple[Path, ...]
    test_paths: tuple[Path, ...]
    compiler_opts: Mapping[str, bool]


def _find_pyproject(cwd: Path) -> Path | None:
    path = cwd.resolve()
    if path.is_file():
        path = path.parent

    for directory in (path, *path.parents):
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def _configuration_error(pyproject: Path, message: str) -> ProjectConfigError:
    return ProjectConfigError(
        f"Invalid Basilisp project configuration in {pyproject}: {message}"
    )


def _resolve_paths(
    pyproject: Path, config: Mapping[str, Any], option_name: str
) -> tuple[Path, ...]:
    paths = config.get(option_name, [])
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise _configuration_error(
            pyproject, f"{option_name} must be an array of strings"
        )

    root = pyproject.parent
    resolved: list[Path] = []
    for path in paths:
        candidate = (root / path).resolve()
        if candidate not in resolved:
            resolved.append(candidate)
    return tuple(resolved)


def _compiler_options(pyproject: Path, config: Mapping[str, Any]) -> Mapping[str, bool]:
    compiler = config.get("compiler", {})
    if not isinstance(compiler, dict):
        raise _configuration_error(pyproject, "compiler must be a table")

    invalid = set(compiler) - _COMPILER_OPTIONS
    if invalid:
        options = ", ".join(sorted(invalid))
        raise _configuration_error(pyproject, f"unknown compiler option(s): {options}")

    for name, value in compiler.items():
        if not isinstance(value, bool):
            raise _configuration_error(
                pyproject, f"compiler option {name} must be a boolean"
            )
    return compiler


def resolve_project(cwd: Path | str) -> ProjectConfig | None:
    """Resolve the nearest ``[tool.basilisp]`` configuration without side effects."""

    pyproject = _find_pyproject(Path(cwd))
    if pyproject is None:
        return None

    try:
        with pyproject.open("rb") as f:
            config = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise _configuration_error(pyproject, "could not parse TOML") from exc

    tool = config.get("tool", {})
    if not isinstance(tool, dict):
        raise _configuration_error(pyproject, "tool must be a table")

    basilisp = tool.get("basilisp")
    if basilisp is None:
        return None
    if not isinstance(basilisp, dict):
        raise _configuration_error(pyproject, "tool.basilisp must be a table")

    return ProjectConfig(
        root=pyproject.parent,
        source_paths=_resolve_paths(pyproject, basilisp, "source-paths"),
        test_paths=_resolve_paths(pyproject, basilisp, "test-paths"),
        compiler_opts=_compiler_options(pyproject, basilisp),
    )
