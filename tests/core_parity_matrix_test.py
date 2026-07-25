from scripts import core_parity_matrix


def test_default_clojure_command_prefers_configured_environment(monkeypatch):
    monkeypatch.setenv("CLOJURE_COMMAND", "custom-clojure -M -e")

    assert [
        "custom-clojure",
        "-M",
        "-e",
    ] == core_parity_matrix._default_clojure_command()


def test_default_clojure_command_prefers_native_clojure(monkeypatch):
    monkeypatch.delenv("CLOJURE_COMMAND", raising=False)
    monkeypatch.setattr(
        core_parity_matrix.shutil, "which", lambda name: name == "clojure"
    )

    assert [
        "clojure",
        "-Sdeps",
        core_parity_matrix.DEFAULT_CLOJURE_SDEPS,
        "-M",
        "-e",
    ] == core_parity_matrix._default_clojure_command()
    assert core_parity_matrix.CLOJURE_VERSION in core_parity_matrix.DEFAULT_CLOJURE_SDEPS


def test_default_clojure_command_falls_back_to_wsl_on_windows(monkeypatch):
    monkeypatch.delenv("CLOJURE_COMMAND", raising=False)
    monkeypatch.setattr(core_parity_matrix.os, "name", "nt")
    monkeypatch.setattr(core_parity_matrix.shutil, "which", lambda name: name == "wsl")

    assert [
        "wsl",
        "-d",
        "Ubuntu-24.04",
        "--",
        "clojure",
        "-Sdeps",
        core_parity_matrix.DEFAULT_CLOJURE_SDEPS,
        "-M",
        "-e",
    ] == core_parity_matrix._default_clojure_command()


def test_status_classifies_shared_missing_and_extension_symbols():
    clojure = {"shared", "missing"}
    basilisp = {"shared", "extension"}

    assert "shared" == core_parity_matrix._status("shared", clojure, basilisp)
    assert "missing-in-basilisp" == core_parity_matrix._status(
        "missing", clojure, basilisp
    )
    assert "basilisp-extension" == core_parity_matrix._status(
        "extension", clojure, basilisp
    )


def test_has_missing_publics_detects_core_gaps():
    rows = list(core_parity_matrix._rows({"shared", "missing"}, {"shared", "extra"}))

    assert core_parity_matrix.has_missing_publics(rows)


def test_main_returns_failure_when_basilisp_is_missing_publics(monkeypatch, capsys):
    commands = []

    def fake_run_publics_command(command):
        commands.append(command)
        expression = command[-1]
        if "clojure.core" in expression:
            return {"shared", "missing"}
        return {"shared"}

    monkeypatch.setattr(
        core_parity_matrix,
        "_default_clojure_command",
        lambda: ["clojure", "-M", "-e"],
    )
    monkeypatch.setattr(
        core_parity_matrix, "_run_publics_command", fake_run_publics_command
    )

    assert 1 == core_parity_matrix.main(["--basilisp-command", "basilisp run -c"])

    output = capsys.readouterr()
    assert "missing-in-basilisp" in output.out
    assert "missing_in_basilisp=1" in output.err
    assert commands == [
        ["clojure", "-M", "-e", core_parity_matrix.CLOJURE_CORE_PUBLICS],
        ["basilisp", "run", "-c", core_parity_matrix.BASILISP_CORE_PUBLICS],
    ]


def test_main_returns_success_when_core_publics_are_complete(monkeypatch):
    monkeypatch.setattr(
        core_parity_matrix,
        "_default_clojure_command",
        lambda: ["clojure", "-M", "-e"],
    )
    monkeypatch.setattr(
        core_parity_matrix,
        "_run_publics_command",
        lambda command: {"shared", "only-basilisp"}
        if "basilisp.core" in command[-1]
        else {"shared"},
    )

    assert 0 == core_parity_matrix.main([])
