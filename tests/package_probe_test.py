from pathlib import Path

from scripts import package_probe


def test_environment_paths_are_platform_specific():
    environment = Path("venv")

    assert package_probe._environment_python(environment, "nt") == Path(
        "venv/Scripts/python.exe"
    )
    assert package_probe._environment_python(environment, "posix") == Path(
        "venv/bin/python"
    )
    assert package_probe._environment_script(environment, "basilisp", "nt") == Path(
        "venv/Scripts/basilisp.exe"
    )
    assert package_probe._environment_script(environment, "basilisp", "posix") == Path(
        "venv/bin/basilisp"
    )


def test_write_smoke_project_uses_pyproject_source_paths(tmp_path):
    project = package_probe._write_smoke_project(tmp_path)

    assert project == tmp_path / "smoke-project"
    assert (project / "pyproject.toml").read_text(encoding="utf-8") == (
        '[tool.basilisp]\nsource-paths = ["src"]\n'
    )
    source = project / "src" / "package_probe" / "sample.lpy"
    assert source.exists()
    assert "(ns package-probe.sample" in source.read_text(encoding="utf-8")
    assert "medley/deep-merge" in source.read_text(encoding="utf-8")


def test_write_smoke_project_is_idempotent_for_wheel_and_sdist(tmp_path):
    first = package_probe._write_smoke_project(tmp_path)
    second = package_probe._write_smoke_project(tmp_path)

    assert first == second
    assert (second / "src" / "package_probe" / "sample.lpy").exists()


def test_verify_cli_smoke_runs_installed_console_script(monkeypatch, tmp_path):
    observed = []

    def run(command, *, cwd, capture_output=False):
        observed.append((command, cwd, capture_output))
        assert capture_output is True

        class Result:
            stdout = f"noise\n{package_probe._EXPECTED_SMOKE_OUTPUT}\n"

        return Result()

    monkeypatch.setattr(package_probe, "_run", run)
    monkeypatch.setattr(
        package_probe,
        "_environment_script",
        lambda environment, script: environment / "bin" / script,
    )

    package_probe._verify_cli_smoke(tmp_path / "venv", tmp_path)

    command, cwd, capture_output = observed[0]
    assert command == [
        str(tmp_path / "venv" / "bin" / "basilisp"),
        "run",
        "-c",
        package_probe._SMOKE_CODE,
        "left",
        "right",
    ]
    assert cwd == tmp_path / "smoke-project"
    assert capture_output is True


def test_verify_cli_smoke_rejects_unexpected_output(monkeypatch, tmp_path):
    def run(command, *, cwd, capture_output=False):
        class Result:
            stdout = "wrong\n"

        return Result()

    monkeypatch.setattr(package_probe, "_run", run)

    try:
        package_probe._verify_cli_smoke(tmp_path / "venv", tmp_path)
    except RuntimeError as exc:
        assert "installed Basilisp CLI smoke output mismatch" in str(exc)
    else:
        raise AssertionError("expected CLI smoke mismatch")
