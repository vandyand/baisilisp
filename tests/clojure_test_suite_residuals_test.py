import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given
from hypothesis import strategies as st

from scripts import clojure_test_suite_residuals as residuals


def _write_suite_files(root: Path, relpaths: tuple[str, ...] | list[str]) -> None:
    for relpath in relpaths:
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("(ns placeholder)\n", encoding="utf-8")


def test_residual_list_is_sorted_unique_and_points_at_core_cljc_files():
    files = residuals.RESIDUAL_CORE_TEST_FILES

    assert tuple(sorted(files)) == files
    assert len(set(files)) == len(files)
    assert all(path.startswith("test/clojure/core_test/") for path in files)
    assert all(path.endswith(".cljc") for path in files)


def test_every_residual_file_has_one_cluster_and_local_evidence():
    clustered = [
        path for cluster in residuals.RESIDUAL_CLUSTERS for path in cluster.files
    ]

    assert tuple(sorted(clustered)) == residuals.RESIDUAL_CORE_TEST_FILES
    assert len(clustered) == len(set(clustered))
    assert all(
        residuals.cluster_for_path(path) is not None
        for path in residuals.RESIDUAL_CORE_TEST_FILES
    )
    assert not residuals.missing_evidence_paths(Path.cwd())

    for cluster in residuals.RESIDUAL_CLUSTERS:
        assert cluster.slug
        assert cluster.classification
        assert cluster.next_action
        assert cluster.evidence_fixtures
        assert cluster.files
        assert all(
            path.startswith("tests/conformance/") for path in cluster.evidence_fixtures
        )


def test_pytest_ignore_args_are_relative_to_suite_root(tmp_path: Path):
    _write_suite_files(tmp_path, residuals.RESIDUAL_CORE_TEST_FILES)

    args = residuals.pytest_ignore_args(tmp_path)

    assert len(args) == len(residuals.RESIDUAL_CORE_TEST_FILES)
    assert args[0] == "--ignore=test/clojure/core_test/byte.cljc"
    assert "--ignore=test/clojure/core_test/conj.cljc" in args
    assert args[-1] == "--ignore=test/clojure/core_test/subs.cljc"
    assert not residuals.missing_paths(tmp_path)


def test_missing_paths_reports_suite_drift(tmp_path: Path):
    _write_suite_files(tmp_path, [residuals.RESIDUAL_CORE_TEST_FILES[0]])

    missing = residuals.missing_paths(tmp_path)

    assert len(missing) == len(residuals.RESIDUAL_CORE_TEST_FILES) - 1
    assert all(isinstance(path, Path) for path in missing)


@given(
    existing=st.lists(
        st.sampled_from(residuals.RESIDUAL_CORE_TEST_FILES),
        unique=True,
    )
)
def test_missing_paths_matches_generated_partial_suite(existing: list[str]):
    with TemporaryDirectory() as dirname:
        root = Path(dirname)
        _write_suite_files(root, existing)

        expected_missing = tuple(
            root / relpath
            for relpath in residuals.RESIDUAL_CORE_TEST_FILES
            if relpath not in existing
        )

        assert expected_missing == residuals.missing_paths(root)


def test_report_covers_every_cluster_and_fixture():
    report = residuals.residual_report()

    for cluster in residuals.RESIDUAL_CLUSTERS:
        assert cluster.slug in report
        for fixture in cluster.evidence_fixtures:
            assert fixture in report
        for path in cluster.files:
            assert path in report


def test_report_mode_does_not_require_external_suite_checkout(
    tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "clojure_test_suite_residuals.py",
            "--suite-root",
            str(tmp_path / "missing-suite"),
            "--repo-root",
            str(Path.cwd()),
            "--report",
        ],
    )

    assert 0 == residuals.main()
    assert "numeric-coercion-expectations" in capsys.readouterr().out
