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


def test_run_tests_workflow_parallelizes_pytest_before_static_checks():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "name: run-tests (${{ matrix.os }}, ${{ matrix.version }}, "
        "${{ matrix.tox-env }})"
    ) in workflow
    assert 'tox run -e "${{ matrix.test-env }}" -- -n auto' in workflow
    assert 'tox run-parallel -p 4 -e "${{ matrix.check-envs }}"' in workflow
    assert workflow.index("Run pytest") < workflow.index("Run static checks")
    assert workflow.index('tox run -e "${{ matrix.test-env }}"') < workflow.index(
        'tox run-parallel -p 4 -e "${{ matrix.check-envs }}"'
    )
    assert "test-env: py310" in workflow
    assert "check-envs: py314-mypy,py314-lint,bandit,format" in workflow
    assert "check-envs: py313-lint" in workflow
