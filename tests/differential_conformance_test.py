from scripts.differential_conformance import _normalize_edn


def test_normalize_edn_compares_maps_independently_of_print_order():
    assert _normalize_edn("{:case :ref :value {:a 1 :b 2}}") == _normalize_edn(
        "{:value {:b 2 :a 1} :case :ref}"
    )
