from pathlib import Path
from shutil import copytree
from subprocess import CompletedProcess

import pytest

import scripts.library_acceptance as acceptance
from scripts.library_acceptance import acceptance_manifest, verify_manifest


def test_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "portable_library"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert '"reader_features": [' in manifest
    assert "clojure.string -> basilisp.string" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_upstream_acceptance_manifest_is_portable_and_checked_in():
    library_root = (
        Path(__file__).parent / "acceptance" / "upstream" / "cognitect-anomalies"
    )
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.spec.alpha -> basilisp.spec.alpha" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_tools_cli_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "tools-cli"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.tools.cli -> basilisp.tools.cli" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )
    production_source = (
        Path(__file__).parents[1] / "src" / "basilisp" / "tools" / "cli.lpy"
    )
    acceptance_source = (
        library_root / "port" / "src" / "basilisp" / "tools" / "cli.cljc"
    )
    assert production_source.read_text(encoding="utf-8") == acceptance_source.read_text(
        encoding="utf-8"
    )


def test_math_combinatorics_acceptance_manifest_is_portable_and_checked_in():
    library_root = (
        Path(__file__).parent / "acceptance" / "upstream" / "math-combinatorics"
    )
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.math.combinatorics -> basilisp.math.combinatorics" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )
    production_source = (
        Path(__file__).parents[1] / "src" / "basilisp" / "math" / "combinatorics.lpy"
    )
    acceptance_source = (
        library_root / "port" / "src" / "basilisp" / "math" / "combinatorics.cljc"
    )
    assert production_source.read_text(encoding="utf-8") == acceptance_source.read_text(
        encoding="utf-8"
    )


def test_medley_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "medley"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "JVM collection dispatch -> Basilisp collection protocols" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_acceptance_library_roots_discovers_checked_in_libraries(tmp_path):
    first = tmp_path / "portable"
    second = tmp_path / "upstream" / "library"
    noise = tmp_path / "missing-manifest"
    for library in (first, second, noise):
        library.mkdir(parents=True)
        (library / "run.cljc").write_text("", encoding="utf-8")
    for library in (first, second):
        (library / "portability-manifest.json").write_text("{}", encoding="utf-8")

    assert acceptance.acceptance_library_roots(tmp_path) == [first, second]


def test_main_all_runs_every_checked_in_library(monkeypatch, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    observed = []

    monkeypatch.setattr(acceptance, "acceptance_library_roots", lambda: [first, second])
    monkeypatch.setattr(
        acceptance,
        "_accept_library",
        lambda library_root, manifest_path, **kwargs: observed.append(
            (library_root, manifest_path, kwargs)
        )
        or True,
    )

    assert 0 == acceptance.main(
        [
            "--all",
            "--clojure-command",
            "clj",
            "--basilisp-command",
            "lpy",
        ]
    )
    assert [
        (first.resolve(), first.resolve() / "portability-manifest.json"),
        (second.resolve(), second.resolve() / "portability-manifest.json"),
    ] == [(library_root, manifest_path) for library_root, manifest_path, _ in observed]
    assert all(
        item[2]["clojure_command"] == "clj" and item[2]["basilisp_command"] == "lpy"
        for item in observed
    )


def test_main_all_stops_on_first_acceptance_mismatch(monkeypatch, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    observed = []

    monkeypatch.setattr(acceptance, "acceptance_library_roots", lambda: [first, second])

    def accept_library(library_root, manifest_path, **kwargs):
        observed.append(library_root)
        return False

    monkeypatch.setattr(acceptance, "_accept_library", accept_library)

    assert 1 == acceptance.main(["--all"])
    assert observed == [first.resolve()]


def test_main_all_rejects_explicit_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(acceptance, "acceptance_library_roots", lambda: [])

    with pytest.raises(SystemExit):
        acceptance.main(["--all", "--manifest", str(tmp_path / "manifest.json")])


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ("[]", "must be an object"),
        ('{"source_root": ".."}', "must stay within the library"),
        ('{"substitutions": ["valid", 1]}', "substitutions must be strings"),
    ],
)
def test_acceptance_settings_reject_invalid_configuration(tmp_path, config, message):
    (tmp_path / "acceptance.json").write_text(config, encoding="utf-8")

    with pytest.raises(RuntimeError, match=message):
        acceptance._acceptance_settings(tmp_path)


def test_verify_manifest_rejects_missing_and_tampered_artifacts(tmp_path):
    source_root = Path(__file__).parent / "acceptance" / "portable_library"
    library_root = tmp_path / "portable_library"
    copytree(source_root, library_root)
    manifest_path = library_root / "portability-manifest.json"

    manifest_path.unlink()
    with pytest.raises(RuntimeError, match="manifest is missing"):
        verify_manifest(library_root, manifest_path)

    manifest_path.write_text(acceptance_manifest(library_root), encoding="utf-8")
    source = library_root / "src" / "acceptance" / "portable_library" / "util.cljc"
    source.write_text(
        source.read_text(encoding="utf-8") + "\n;; tampered\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="manifest is stale"):
        verify_manifest(library_root, manifest_path)


def test_acceptance_run_uses_only_the_final_edn_summary(monkeypatch, tmp_path):
    runner = tmp_path / "run.cljc"
    monkeypatch.setattr(
        acceptance.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(
            args,
            0,
            stdout="Testing example\n{:pass 2 :fail 0}\n",
            stderr="",
        ),
    )

    assert [acceptance._normalize_edn("{:pass 2 :fail 0}")] == acceptance._run(
        "basilisp run", runner, label="Basilisp"
    )


@pytest.mark.parametrize("output", ["", "Testing example\n{:pass 1} {:fail 0}\n"])
def test_acceptance_run_rejects_missing_or_malformed_final_summary(
    monkeypatch, tmp_path, output
):
    runner = tmp_path / "run.cljc"
    monkeypatch.setattr(
        acceptance.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args, 0, stdout=output, stderr=""),
    )

    with pytest.raises(RuntimeError):
        acceptance._run("basilisp run", runner, label="Basilisp")


def test_acceptance_run_surfaces_runtime_failure_stderr(monkeypatch, tmp_path):
    runner = tmp_path / "run.cljc"
    monkeypatch.setattr(
        acceptance.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(
            args, 9, stdout="", stderr="test namespace exploded"
        ),
    )

    with pytest.raises(
        RuntimeError, match="(?s)Basilisp acceptance run failed.*exploded"
    ):
        acceptance._run("basilisp run", runner, label="Basilisp")


@pytest.mark.slow
def test_checked_in_acceptance_libraries_execute_under_available_runtimes():
    try:
        result = acceptance.main(["--all"])
    except RuntimeError as exc:
        if "command is unavailable" in str(exc):
            pytest.skip(str(exc))
        raise

    assert result == 0
