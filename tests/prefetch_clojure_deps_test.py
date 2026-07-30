from subprocess import CompletedProcess

from scripts import prefetch_clojure_deps


def test_direct_sdeps_unescapes_shell_quoted_versions():
    assert (
        prefetch_clojure_deps._direct_sdeps(
            'org.clojure/data.json {:mvn/version \\"2.5.1\\"}'
        )
        == 'org.clojure/data.json {:mvn/version "2.5.1"}'
    )


def test_prefetch_retries_until_success(monkeypatch):
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return CompletedProcess(command, 1 if len(calls) == 1 else 0)

    monkeypatch.setattr(prefetch_clojure_deps.subprocess, "run", fake_run)
    monkeypatch.setattr(prefetch_clojure_deps.time, "sleep", lambda _seconds: None)

    assert (
        prefetch_clojure_deps.main(
            ["library", "--attempts", "2", "--delay-seconds", "0"]
        )
        == 0
    )
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert calls[0][-1] == "-P"
