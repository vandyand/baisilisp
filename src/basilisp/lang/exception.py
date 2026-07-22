import functools
import sys
import traceback
from types import TracebackType

import attr

from basilisp.lang.diagnostics import exception_data
from basilisp.lang.interfaces import IExceptionInfo, IPersistentMap
from basilisp.lang.obj import lrepr


@attr.define(repr=False, str=False)
class ExceptionInfo(IExceptionInfo):
    message: str
    data: IPersistentMap
    # Clojure exposes this through ex-cause, not value equality. Excluding it
    # also avoids recursively comparing a potentially cyclic Python chain.
    cause: BaseException | None = attr.field(default=None, eq=False)

    def __attrs_post_init__(self) -> None:
        """Install Clojure's explicit ex-info cause on Python's exception chain."""
        if self.cause is not None:
            self.__cause__ = self.cause

    def __repr__(self):
        return (
            f"basilisp.lang.exception.ExceptionInfo({self.message}, {lrepr(self.data)})"
        )

    def __str__(self):
        return f"{self.message} {lrepr(self.data)}"


@functools.singledispatch
def format_exception(  # pylint: disable=unused-argument
    e: BaseException | None,
    tp: type[BaseException] | None = None,
    tb: TracebackType | None = None,
    disable_color: bool | None = None,
) -> list[str]:
    """Format an exception into something readable, returning a list of newline
    terminated strings.

    For the majority of Python exceptions, this will just be the result from calling
    `traceback.format_exception`. For Basilisp specific compilation errors, a custom
    output will be returned.

    If `disable_color` is True, no color formatting should be applied to the source
    code."""
    if isinstance(e, BaseException):
        if tp is None:
            tp = type(e)
        if tb is None:
            tb = e.__traceback__
    return traceback.format_exception(tp, e, tb)


def print_exception(
    e: BaseException | None,
    tp: type[BaseException] | None = None,
    tb: TracebackType | None = None,
) -> None:
    """Print the given exception `e` using Basilisp's own exception formatting.

    For the majority of exception types, this should be identical to the base Python
    traceback formatting. `basilisp.lang.compiler.CompilerException` and
    `basilisp.lang.reader.SyntaxError` have special handling to print useful information
    on exceptions."""
    print("".join(format_exception(e, tp, tb)), file=sys.stderr)
    if isinstance(e, BaseException):
        print(f"Basilisp diagnostic: {lrepr(exception_data(e))}", file=sys.stderr)
