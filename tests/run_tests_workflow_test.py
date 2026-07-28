from pathlib import Path

WORKFLOW = Path(".github/workflows/run-tests.yml")


def test_run_tests_workflow_installs_clojure_for_namespace_audits():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    audit_step = "Run standard namespace parity audits"

    assert "actions/setup-java@v5" in workflow
    assert "distribution: temurin" in workflow
    assert "java-version: '21'" in workflow
    assert "DeLaGuardo/setup-clojure@13.6.1" in workflow
    assert "cli: latest" in workflow
    assert workflow.index("actions/setup-java@v5") < workflow.index(audit_step)
    assert workflow.index("DeLaGuardo/setup-clojure@13.6.1") < workflow.index(
        audit_step
    )


def test_run_tests_workflow_gates_core_and_standard_namespace_parity():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "scripts/core_parity_matrix.py" in workflow
    assert "scripts/core_semantic_fixture_coverage.py" in workflow
    assert "scripts/semantic_fixture_coverage.py" in workflow
    assert "--min-coverage 100" in workflow
    assert "scripts/standard_namespace_surface_matrix.py" in workflow
    assert "scripts/standard_namespace_inventory.py" in workflow
    assert "--verify-clojure --verify-basilisp" in workflow
    assert "--verify-legacy-source" in workflow
    assert "--verify-source-omissions" in workflow
    assert "--verify-discovered-resources" in workflow
    assert "core-parity.csv" in workflow
    assert "core-semantic-coverage.csv" in workflow
    assert "standard-namespace-surface.csv" in workflow
    assert "standard-namespace-inventory.csv" in workflow


def test_run_tests_workflow_runs_bounded_pytest_publish_gate():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "name: run-tests (${{ matrix.os }}, ${{ matrix.version }}, "
        "${{ matrix.tox-env }})"
    ) in workflow
    assert (
        'tox run -e "${{ matrix.test-env }}" -- tests/basilisp/core_test.py '
        "tests/basilisp/reader_test.py tests/basilisp/runtime_test.py "
        "tests/basilisp/string_escape_test.py "
        "tests/basilisp/core/test_core_fns.lpy "
        "tests/basilisp/core/test_printing_fns.lpy -q"
    ) in workflow
    assert 'tox run -e "${{ matrix.test-env }}" -- \\' not in workflow
    assert "tests/basilisp/core_test.py" in workflow
    assert "tests/basilisp/reader_test.py" in workflow
    assert "tests/basilisp/runtime_test.py" in workflow
    assert "tests/basilisp/string_escape_test.py" in workflow
    assert "tests/basilisp/core/test_core_fns.lpy" in workflow
    assert "tests/basilisp/core/test_printing_fns.lpy" in workflow
    assert "test-env: py310" in workflow
    assert "Run static checks" not in workflow
    assert "tox run-parallel" not in workflow
    assert "check-envs:" not in workflow
    assert "bandit" not in workflow
    assert "py314-mypy" not in workflow
    assert "py314-lint" not in workflow


def test_run_tests_workflow_keeps_release_smoke_jobs_bounded():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "fail-fast: false" in workflow
    assert "run-pypy-tests:" in workflow
    assert "min-deps-test:" in workflow
    assert "timeout-minutes: 90" in workflow
    assert workflow.count("timeout-minutes: 60") >= 2
    assert "tests/basilisp/string_escape_test.py" in workflow
    assert "tests/basilisp/core/test_printing_fns.lpy" in workflow
    assert "tox run -- tests/basilisp/core_test.py" in workflow
    assert "tox run -- \\" not in workflow
