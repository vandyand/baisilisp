from pathlib import Path

WORKFLOW = Path(".github/workflows/run-clojure-test-suite.yml")


def test_clojure_test_suite_workflow_verifies_residual_evidence_before_ignores():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "actions/setup-java@v5" in workflow
    assert "distribution: temurin" in workflow
    assert "java-version: '21'" in workflow
    assert "DeLaGuardo/setup-clojure@13.6.1" in workflow
    assert "cli: latest" in workflow
    assert "--verify-evidence" in workflow
    assert "--disable-basilisp-ns-cache" in workflow
    assert '--basilisp-command "$BASILISP_COMMAND"' in workflow
    assert workflow.index("--verify-evidence") < workflow.index("--pytest-ignore-args")
