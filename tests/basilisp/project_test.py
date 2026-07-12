from pathlib import Path

import pytest

from basilisp import project


def test_resolve_project_returns_none_without_pyproject(tmp_path: Path):
    assert project.resolve_project(tmp_path) is None


def test_resolve_project_reports_invalid_toml(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.basilisp\n")

    with pytest.raises(project.ProjectConfigError, match="could not parse TOML"):
        project.resolve_project(tmp_path)


def test_resolve_project_finds_nearest_pyproject_and_resolves_paths(tmp_path: Path):
    root = tmp_path / "project"
    child = root / "nested" / "directory"
    child.mkdir(parents=True)
    (root / "pyproject.toml").write_text("""
[tool.basilisp]
source-paths = ["src", "generated", "src"]
test-paths = ["tests"]

[tool.basilisp.compiler]
warn-on-arity-mismatch = false
""".strip())

    resolved = project.resolve_project(child)

    assert resolved is not None
    assert resolved.root == root
    assert resolved.source_paths == (root / "src", root / "generated")
    assert resolved.test_paths == (root / "tests",)
    assert resolved.compiler_opts == {"warn-on-arity-mismatch": False}


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ('source-paths = "src"', "source-paths must be an array of strings"),
        ("source-paths = [1]", "source-paths must be an array of strings"),
        (
            '[tool.basilisp.compiler]\nwarn-on-arity-mismatch = "true"',
            "must be a boolean",
        ),
        ("[tool.basilisp.compiler]\nunknown-option = true", "unknown compiler option"),
    ],
)
def test_resolve_project_rejects_invalid_configuration(
    tmp_path: Path, config: str, message: str
):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(f"[tool.basilisp]\n{config}\n")

    with pytest.raises(project.ProjectConfigError, match=message):
        project.resolve_project(tmp_path)
