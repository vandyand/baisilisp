from pathlib import Path


WORKFLOW = Path(".github/workflows/run-parity-proofs.yml")


def test_parity_proofs_workflow_runs_sharded_differential_conformance():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    differential_job = workflow.index("differential-conformance:")

    assert "0, 1, 2, 3, 4, 5, 6, 7" in workflow
    assert "24, 25, 26, 27, 28, 29, 30, 31" in workflow
    assert "max-parallel: 8" in workflow
    assert "scripts/differential_conformance.py" in workflow
    assert "--disable-basilisp-ns-cache" in workflow
    assert "--shard-count 32" in workflow
    assert "--shard-index ${{ matrix.shard-index }}" in workflow
    assert '--basilisp-command ".tox/py314/bin/basilisp run"' in workflow
    assert workflow.index("scripts/differential_conformance.py") > differential_job


def test_parity_proofs_workflow_runs_sharded_library_acceptance():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    library_job = workflow.index("library-acceptance:")

    assert "shard-index: [0, 1, 2]" in workflow
    assert "scripts/library_acceptance.py" in workflow
    assert "--all" in workflow
    assert "--disable-basilisp-ns-cache" in workflow
    assert "--shard-count 3" in workflow
    assert "--shard-index ${{ matrix.shard-index }}" in workflow
    assert '--basilisp-command ".tox/py314/bin/basilisp run"' in workflow
    assert workflow.index("scripts/library_acceptance.py") > library_job


def test_parity_proofs_workflow_installs_java_clojure_and_tox_for_each_job():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert workflow.count("actions/setup-python@v6") == 2
    assert workflow.count("python-version: '3.14'") == 2
    assert workflow.count("actions/setup-java@v5") == 2
    assert workflow.count("distribution: temurin") == 2
    assert workflow.count("java-version: '21'") == 2
    assert workflow.count("cache: maven") == 2
    assert workflow.count("DeLaGuardo/setup-clojure@13.6.1") == 2
    assert workflow.count("cli: latest") == 2
    assert workflow.count("pip install tox") == 2


def test_parity_proofs_workflow_runs_on_pr_push_and_schedule():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "branches: [ main ]" in workflow
    assert "schedule:" in workflow
