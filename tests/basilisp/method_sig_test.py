import functools
import inspect
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import basilisp.core as core


def _annotations(signature: object) -> list[object] | None:
    result = core.method_sig(signature)
    params = result[1]
    return None if params is None else list(params)


def test_method_sig_projects_annotated_callable_without_invoking_it():
    calls = 0

    def annotated(
        first: int, /, second: str = "", *rest: bytes, flag: bool, **extra: float
    ) -> dict[str, int]:
        nonlocal calls
        calls += 1
        raise AssertionError("method-sig must not invoke its argument")

    result = core.method_sig(annotated)

    assert result[0] == "annotated"
    assert _annotations(annotated) == [int, str, bytes, bool, float]
    assert result[2] == dict[str, int]
    assert calls == 0


def test_method_sig_preserves_inspect_receiver_semantics_for_descriptors():
    class Descriptor:
        def instance(self, value: int, label: str = "") -> bytes:
            raise AssertionError("must not be invoked")

        @classmethod
        def class_method(cls, value: float) -> bool:
            raise AssertionError("must not be invoked")

        @staticmethod
        def static_method(value: bytes) -> int:
            raise AssertionError("must not be invoked")

    assert _annotations(Descriptor.instance) == [None, int, str]
    assert _annotations(Descriptor().instance) == [int, str]
    assert _annotations(Descriptor.class_method) == [float]
    assert _annotations(Descriptor.static_method) == [bytes]
    assert core.method_sig(Descriptor().instance)[2] is bytes
    assert core.method_sig(Descriptor.class_method)[2] is bool
    assert core.method_sig(Descriptor.static_method)[2] is int


def test_method_sig_handles_unannotated_and_zero_parameter_host_callables():
    def no_parameters():
        return None

    assert core.method_sig(no_parameters)[1] is None
    assert core.method_sig(no_parameters)[2] is None
    assert core.method_sig(len)[0] == "len"
    assert _annotations(len) == [None]
    assert core.method_sig(len)[2] is None


def test_method_sig_rejects_non_callable_anonymous_and_uninspectable_values():
    class MissingName:
        def __call__(self, value: int) -> int:
            return value

    class BrokenSignature:
        __name__ = "broken_signature"

        @property
        def __signature__(self):
            raise ValueError("deliberately malformed")

        def __call__(self):
            return None

    with pytest.raises(TypeError, match="requires a callable"):
        core.method_sig(42)
    with pytest.raises(TypeError, match="string __name__"):
        core.method_sig(MissingName())
    with pytest.raises(
        TypeError, match="cannot inspect callable: .*deliberately malformed"
    ):
        core.method_sig(BrokenSignature())
    with pytest.raises(TypeError, match="string __name__"):
        core.method_sig(functools.partial(len, []))


ANNOTATIONS: tuple[Any, ...] = (
    inspect.Signature.empty,
    None,
    bool,
    bytes,
    float,
    int,
    str,
    list[str],
    "ForwardReference",
)


@given(
    parameter_annotations=st.lists(
        st.sampled_from(ANNOTATIONS), min_size=0, max_size=24
    ),
    return_annotation=st.sampled_from(ANNOTATIONS),
)
@settings(max_examples=150, deadline=None)
def test_method_sig_fuzzes_annotated_python_signatures(
    parameter_annotations: list[Any], return_annotation: Any
):
    def fuzz_target(*args, **kwargs):
        return args, kwargs

    fuzz_target.__signature__ = inspect.Signature(
        [
            inspect.Parameter(
                f"parameter_{index}",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=annotation,
            )
            for index, annotation in enumerate(parameter_annotations)
        ],
        return_annotation=return_annotation,
    )

    result = core.method_sig(fuzz_target)
    expected_parameters = [
        None if annotation is inspect.Signature.empty else annotation
        for annotation in parameter_annotations
    ]
    expected_return = (
        None if return_annotation is inspect.Signature.empty else return_annotation
    )

    assert result[0] == "fuzz_target"
    assert (None if result[1] is None else list(result[1])) == (
        expected_parameters or None
    )
    assert result[2] == expected_return


def test_method_sig_is_safe_under_concurrent_reflection():
    def concurrent_target(value: int, label: str = "") -> tuple[int, str]:
        raise AssertionError("method-sig must not invoke its argument")

    expected = ("concurrent_target", [int, str], tuple[int, str])

    def reflect(_index: int) -> tuple[str, list[object] | None, object]:
        result = core.method_sig(concurrent_target)
        return result[0], None if result[1] is None else list(result[1]), result[2]

    with ThreadPoolExecutor(max_workers=16) as pool:
        assert list(pool.map(reflect, range(2_048))) == [expected] * 2_048
