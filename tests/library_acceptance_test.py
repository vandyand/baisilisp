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
