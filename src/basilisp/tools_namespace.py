"""Runtime helpers for the portable ``tools.namespace`` refresh loop."""

from __future__ import annotations

import importlib
import os
import sys
from typing import Any

from basilisp import importer
from basilisp.lang import runtime
from basilisp.lang import symbol as sym
from basilisp.lang.util import munge


def remove_namespace(namespace: Any) -> None:
    """Forget a loaded namespace and its generated module before re-requiring it.

    ``Namespace.remove`` alone deliberately leaves ``sys.modules`` untouched;
    a development refresh needs to remove both caches so that Python's import
    machinery executes the current source again.
    """

    name = str(namespace)
    ns = runtime.Namespace.get(sym.symbol(name))
    if ns is not None:
        source_path = getattr(ns.module, "__file__", None)
        if source_path:
            # The importer intentionally validates bytecode only at second
            # granularity. A development refresh must still observe two same-
            # size edits made within that second, so discard its cache entry.
            try:
                os.remove(
                    importer._cache_from_source(source_path)
                )  # pylint: disable=protected-access
            except FileNotFoundError:
                pass
    runtime.Namespace.remove(sym.symbol(name))
    sys.modules.pop(munge(name), None)
    importlib.invalidate_caches()
