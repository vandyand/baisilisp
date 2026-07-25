from pathlib import Path

import conftest


def test_test_prefixed_conformance_fixtures_are_not_pytest_collected():
    ignored = {Path(path) for path in conftest.collect_ignore}

    assert set(Path("tests/conformance").glob("test_*.cljc")) <= ignored
