from scripts import core_parity_matrix


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
