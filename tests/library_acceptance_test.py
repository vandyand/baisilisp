from pathlib import Path

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
