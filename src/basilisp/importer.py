import importlib
import importlib.util
import logging
import marshal
import os
import os.path
import sys
import tempfile
import threading
import types
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from functools import lru_cache
from importlib.abc import MetaPathFinder, SourceLoader
from importlib.machinery import ModuleSpec
from typing import Any, cast

from typing_extensions import TypedDict

from basilisp.lang import compiler as compiler
from basilisp.lang import reader as reader
from basilisp.lang import runtime as runtime
from basilisp.lang import symbol as sym
from basilisp.lang import vector as vec
from basilisp.lang.runtime import BasilispModule
from basilisp.lang.typing import ReaderForm
from basilisp.lang.util import demunge, munge
from basilisp.util import timed

_NO_CACHE_ENVVAR = "BASILISP_DO_NOT_CACHE_NAMESPACES"

MAGIC_NUMBER = (1149).to_bytes(2, "little") + b"\r\n"
_AOT_MAGIC_NUMBER = (1150).to_bytes(2, "little") + b"\r\n"
_COMPILE_PATH_VAR_NAME = "*compile-path*"

logger = logging.getLogger(__name__)


def _r_long(int_bytes: bytes) -> int:
    """Convert 4 bytes in little-endian to an integer."""
    return int.from_bytes(int_bytes, "little")


def _w_long(x: int) -> bytes:
    """Convert a 32-bit integer to little-endian."""
    return (int(x) & 0xFFFFFFFF).to_bytes(4, "little")


def _basilisp_bytecode(
    mtime: int, source_size: int, code: list[types.CodeType]
) -> bytes:
    """Return the bytes for a Basilisp bytecode cache file."""
    data = bytearray(MAGIC_NUMBER)
    data.extend(_w_long(mtime))
    data.extend(_w_long(source_size))
    data.extend(marshal.dumps(code))
    return bytes(data)


def _get_basilisp_bytecode(
    fullname: str, mtime: int, source_size: int, cache_data: bytes
) -> list[types.CodeType]:
    """Unmarshal the bytes from a Basilisp bytecode cache file, validating the
    file header prior to returning. If the file header does not match, throw
    an exception."""
    exc_details = {"name": fullname}
    magic = cache_data[:4]
    raw_timestamp = cache_data[4:8]
    raw_size = cache_data[8:12]
    if magic != MAGIC_NUMBER:
        message = (
            f"Incorrect magic number ({magic!r}) in {fullname}; "
            f"expected {MAGIC_NUMBER!r}"
        )
        logger.debug(message)
        raise ImportError(message, **exc_details)
    elif len(raw_timestamp) != 4:
        message = f"Reached EOF while reading timestamp in {fullname}"
        logger.debug(message)
        raise EOFError(message)
    elif _r_long(raw_timestamp) != mtime:
        message = f"Non-matching timestamp ({_r_long(raw_timestamp)}) in {fullname} bytecode cache; expected {mtime}"
        logger.debug(message)
        raise ImportError(message, **exc_details)
    elif len(raw_size) != 4:
        message = f"Reached EOF while reading size of source in {fullname}"
        logger.debug(message)
        raise EOFError(message)
    elif _r_long(raw_size) != source_size:
        message = f"Non-matching filesize ({_r_long(raw_size)}) in {fullname} bytecode cache; expected {source_size}"
        logger.debug(message)
        raise ImportError(message, **exc_details)

    return marshal.loads(cache_data[12:])  # nosec 6302


def _basilisp_aot_bytecode(source_filename: str, code: list[types.CodeType]) -> bytes:
    """Return a standalone Basilisp ahead-of-time artifact.

    Ordinary ``.lpyc`` cache files are deliberately tied to the source file's
    timestamp and size. AOT artifacts instead carry the original source path
    only for diagnostics and can be imported after that source is unavailable.
    As with Python ``.pyc`` files, artifacts are trusted executable bytecode
    and are local to a compatible Python/Basilisp installation.
    """
    return _AOT_MAGIC_NUMBER + marshal.dumps((source_filename, code))


def _get_basilisp_aot_bytecode(
    fullname: str, cache_data: bytes
) -> tuple[str, list[types.CodeType]]:
    """Unmarshal and validate a standalone Basilisp AOT artifact."""
    if cache_data[:4] != _AOT_MAGIC_NUMBER:
        raise ImportError(
            f"Incorrect AOT magic number ({cache_data[:4]!r}) in {fullname}; "
            f"expected {_AOT_MAGIC_NUMBER!r}",
            name=fullname,
        )
    try:
        source_filename, code = marshal.loads(cache_data[4:])  # nosec 6302
    except (EOFError, TypeError, ValueError) as e:
        raise ImportError(f"Invalid Basilisp AOT artifact for {fullname}") from e
    if (
        not isinstance(source_filename, str)
        or not isinstance(code, list)
        or not all(isinstance(c, types.CodeType) for c in code)
    ):
        raise ImportError(f"Invalid Basilisp AOT artifact for {fullname}")
    return source_filename, code


def _cache_from_source(path: str) -> str:
    """Return the path to the cached file for the given path. The original path
    does not have to exist."""
    cache_path, cache_file = os.path.split(importlib.util.cache_from_source(path))
    filename, _ = os.path.splitext(cache_file)
    return os.path.join(cache_path, filename + ".lpyc")


def _aot_from_namespace(compile_path: str, fullname: str, is_package: bool) -> str:
    """Return the standalone artifact path for a munged Python module name."""
    components = fullname.split(".")
    if is_package:
        return os.path.join(compile_path, *components, "__init__.lpyc")
    return os.path.join(compile_path, *components) + ".lpyc"


def _is_within(path: str, parent: str) -> bool:
    """Return whether ``path`` is nested under ``parent``, across Windows drives."""
    try:
        return os.path.commonpath(
            (os.path.abspath(path), os.path.abspath(parent))
        ) == os.path.abspath(parent)
    except ValueError:
        return False


@lru_cache
def _is_package(path: str) -> bool:
    """Return True if path should be considered a Basilisp (and consequently
    a Python) package.

    A path would be considered a package if it contains at least one Basilisp
    or Python code file."""
    for _, _, files in os.walk(path):
        for file in files:
            if file.endswith(".lpy") or file.endswith(".py") or file.endswith(".cljc"):
                return True
    return False


@lru_cache
def _is_namespace_package(path: str) -> bool:
    """Return True if the current directory is a namespace Basilisp package.

    Basilisp namespace packages are directories containing no __init__.py or
    __init__.lpy files and at least one other Basilisp code file."""
    no_inits = True
    has_basilisp_files = False
    _, _, files = next(os.walk(path))
    for file in files:
        if file in {"__init__.lpy", "__init__.py"}:
            no_inits = False
        elif file.endswith(".lpy") or file.endswith(".cljc"):
            has_basilisp_files = True
    return no_inits and has_basilisp_files


class ImporterCacheEntry(TypedDict, total=False):
    spec: ModuleSpec
    module: BasilispModule
    bytecode: list[types.CodeType]


class BasilispImporter(  # type: ignore[misc]  # pylint: disable=abstract-method
    MetaPathFinder, SourceLoader
):
    """Python import hook to allow directly loading Basilisp code within
    Python."""

    def __init__(self):
        self._cache: MutableMapping[str, ImporterCacheEntry] = {}
        self._aot_lock = threading.RLock()

    @staticmethod
    def _compile_path() -> str | None:
        """Return the currently bound Basilisp AOT output path, if available."""
        compile_path_var = runtime.Var.find_in_ns(
            runtime.CORE_NS_SYM, sym.symbol(_COMPILE_PATH_VAR_NAME)
        )
        if compile_path_var is None:
            return None
        try:
            compile_path = os.fspath(compile_path_var.value)
        except TypeError:
            return None
        return compile_path if isinstance(compile_path, str) and compile_path else None

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: types.ModuleType | None = None,
    ) -> ModuleSpec | None:
        """Find the ModuleSpec for the specified Basilisp module.

        Returns None if the module is not a Basilisp module to allow import processing to continue.
        """
        package_components = fullname.split(".")
        if not path:
            path = sys.path
            module_name = package_components
        else:
            module_name = [package_components[-1]]

        for entry in path:
            root_path = os.path.join(entry, *module_name)
            filenames = [
                f"{os.path.join(root_path, '__init__')}.lpy",
                f"{root_path}.lpy",
                f"{os.path.join(root_path, '__init__')}.cljc",
                f"{root_path}.cljc",
            ]
            for filename in filenames:
                if os.path.isfile(filename):
                    state = {
                        "fullname": fullname,
                        "filename": filename,
                        "path": entry,
                        "target": target,
                        "cache_filename": _cache_from_source(filename),
                    }
                    logger.debug(
                        f"Found potential Basilisp module '{fullname}' in file '{filename}'"
                    )
                    is_package = filename.endswith("__init__.lpy") or _is_package(
                        root_path
                    )
                    spec = ModuleSpec(
                        fullname,
                        self,
                        origin=filename,
                        loader_state=state,
                        is_package=is_package,
                    )
                    # The Basilisp loader can find packages regardless of
                    # submodule_search_locations, but the Python loader cannot.
                    # Set this to the root path to allow the Python loader to
                    # load submodules of Basilisp "packages".
                    if is_package:
                        assert (
                            spec.submodule_search_locations is not None
                        ), "Package module spec must have submodule_search_locations list"
                        spec.submodule_search_locations.append(root_path)
                    return spec

        # Source always wins over an AOT artifact. This keeps edit/reload cycles
        # unsurprising while still allowing a deployed artifact tree to be loaded
        # without source files on sys.path.
        compile_path = self._compile_path()
        aot_entries: Sequence[str] = ()
        if compile_path is not None:
            if path is sys.path:
                aot_entries = (compile_path,)
            else:
                compile_path_abs = os.path.abspath(compile_path)
                aot_entries = tuple(
                    entry for entry in path if _is_within(entry, compile_path_abs)
                )
        for entry in aot_entries:
            root_path = os.path.join(entry, *module_name)
            filenames = [
                os.path.join(root_path, "__init__.lpyc"),
                f"{root_path}.lpyc",
            ]
            for aot_filename in filenames:
                if not os.path.isfile(aot_filename):
                    continue
                source_filename, _ = _get_basilisp_aot_bytecode(
                    fullname, self.get_data(aot_filename)
                )
                is_package = aot_filename.endswith("__init__.lpyc")
                state = {
                    "fullname": fullname,
                    "filename": source_filename,
                    "path": entry,
                    "target": target,
                    "aot_filename": aot_filename,
                }
                logger.debug(
                    "Found Basilisp AOT module '%s' in artifact '%s'",
                    fullname,
                    aot_filename,
                )
                spec = ModuleSpec(
                    fullname,
                    self,
                    origin=aot_filename,
                    loader_state=state,
                    is_package=is_package,
                )
                if is_package:
                    assert spec.submodule_search_locations is not None
                    spec.submodule_search_locations.append(root_path)
                return spec

        for entry in path:
            root_path = os.path.join(entry, *module_name)
            if os.path.isdir(root_path):
                if _is_namespace_package(root_path):
                    return ModuleSpec(fullname, None, is_package=True)
        return None

    def invalidate_caches(self) -> None:
        super().invalidate_caches()
        self._cache = {}

    def _cache_bytecode(self, source_path: str, cache_path: str, data: bytes) -> None:
        self.set_data(cache_path, data)

    def _write_aot_bytecode(self, aot_path: str, data: bytes) -> None:
        """Atomically publish an AOT artifact so concurrent readers see all or none."""
        # Windows does not permit two simultaneous replacements of one target;
        # serializing publication also keeps the operation atomic for callers
        # sharing an importer instance.
        with self._aot_lock:
            directory = os.path.dirname(aot_path)
            os.makedirs(directory, exist_ok=True)
            temp_name: str | None = None
            try:
                with tempfile.NamedTemporaryFile(dir=directory, delete=False) as temp:
                    temp_name = temp.name
                    temp.write(data)
                os.replace(temp_name, aot_path)
            finally:
                if temp_name is not None:
                    try:
                        os.unlink(temp_name)
                    except FileNotFoundError:
                        pass

    def path_stats(self, path: str) -> Mapping[str, Any]:
        stat = os.stat(path)
        return {"mtime": int(stat.st_mtime), "size": stat.st_size}

    def get_data(self, path: str) -> bytes:
        with open(path, mode="r+b") as f:
            return f.read()

    def set_data(self, path: str, data: bytes) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode="w+b") as f:
            f.write(data)

    def get_filename(self, fullname: str) -> str:
        try:
            cached = self._cache[fullname]
        except KeyError as e:
            if (spec := self.find_spec(fullname, None)) is None:
                raise ImportError(f"Could not import module '{fullname}'") from e
        else:
            spec = cached["spec"]
            assert spec is not None, "spec must be defined here"
        return spec.loader_state["filename"]

    def get_code(self, fullname: str) -> types.CodeType | None:
        """Return code to load a Basilisp module.

        This function is part of the ABC for `importlib.abc.ExecutionLoader` which is
        what Python uses to execute modules at the command line as `python -m module`.
        """
        core_ns = runtime.Namespace.get(runtime.CORE_NS_SYM)
        assert core_ns is not None

        with runtime.ns_bindings("basilisp.namespace-executor") as ns:
            ns.refer_all(core_ns)

            # Set the *main-ns* variable to the current namespace.
            main_ns_var = core_ns.find(sym.symbol(runtime.MAIN_NS_VAR_NAME))
            assert main_ns_var is not None
            main_ns_var.bind_root(sym.symbol(demunge(fullname)))

            # Set command line args passed to the module
            if pyargs := sys.argv[1:]:
                cli_args_var = core_ns.find(
                    sym.symbol(runtime.COMMAND_LINE_ARGS_VAR_NAME)
                )
                assert cli_args_var is not None
                cli_args_var.bind_root(vec.vector(pyargs))

            # Basilisp can only ever product multiple `types.CodeType` objects for any
            # given module because it compiles each form as a separate unit, but
            # `ExecutionLoader.get_code` expects a single `types.CodeType` object. To
            # simulate this requirement, we generate a single `(load "...")` to execute
            # in a synthetic namespace.
            #
            # The target namespace is free to interpret
            code: list[types.CodeType] = []
            path = "/" + "/".join(fullname.split("."))
            try:
                compiler.load(
                    path,
                    compiler.CompilerContext(
                        filename="<Basilisp Namespace Executor>",
                        opts=runtime.get_compiler_opts(),
                    ),
                    ns,
                    collect_bytecode=code.append,
                )
            except Exception as e:
                raise ImportError(f"Could not import module '{fullname}'") from e
            else:
                assert len(code) == 1
                return code[0]

    def create_module(self, spec: ModuleSpec) -> BasilispModule:
        # If a namespace was created dynamically before being require'd, then
        # a module will already exist for the namespace. References may already
        # have been made to the contents of that module. Reusing it rather than
        # starting new allows both dynamically created namespaces and namespaces
        # defined in files to coexist.
        if (ns := runtime.Namespace.get(sym.symbol(demunge(spec.name)))) is not None:
            logger.debug(f"Reusing existing module for namespace '{ns}'")
            mod = ns.module
            assert isinstance(mod, BasilispModule)
        else:
            logger.debug(f"Creating Basilisp module '{spec.name}'")
            mod = BasilispModule(spec.name)

        mod.__file__ = spec.loader_state["filename"]
        mod.__loader__ = spec.loader
        mod.__package__ = spec.parent
        mod.__spec__ = spec
        self._cache[spec.name] = {"spec": spec}
        return mod

    def _exec_cached_module(
        self,
        fullname: str,
        loader_state: Mapping[str, str],
        path_stats: Mapping[str, int],
        module: BasilispModule,
    ) -> list[types.CodeType]:
        """Load and execute a cached Basilisp module."""
        filename = loader_state["filename"]
        cache_filename = loader_state["cache_filename"]

        with timed(
            lambda duration: logger.debug(
                f"Loaded cached Basilisp module '{fullname}' in {duration / 1000000}ms"
            )
        ):
            logger.debug(f"Checking for cached Basilisp module '{fullname}''")
            cache_data = self.get_data(cache_filename)
            cached_code = _get_basilisp_bytecode(
                fullname, path_stats["mtime"], path_stats["size"], cache_data
            )
            compiler.compile_bytecode(
                cached_code,
                compiler.GeneratorContext(
                    filename=filename, opts=runtime.get_compiler_opts()
                ),
                compiler.PythonASTOptimizer(),
                module,
            )
            return cached_code

    def _exec_module(
        self,
        fullname: str,
        loader_state: Mapping[str, str],
        path_stats: Mapping[str, int],
        module: BasilispModule,
    ) -> list[types.CodeType]:
        """Load and execute a non-cached Basilisp module."""
        filename = loader_state["filename"]
        cache_filename = loader_state["cache_filename"]

        with timed(
            lambda duration: logger.debug(
                f"Loaded Basilisp module '{fullname}' in {duration / 1000000}ms"
            )
        ):
            # During compilation, bytecode objects are added to the list which is
            # passed to the compiler. The collected bytecodes will be used to generate
            # an .lpyc file for caching the compiled file.
            all_bytecode: list[types.CodeType] = []

            logger.debug(f"Reading and compiling Basilisp module '{fullname}'")
            # Cast to basic ReaderForm since the reader can never return a reader conditional
            # form unprocessed in internal usage. There are reader settings which permit
            # callers to leave unprocessed reader conditionals in the stream, however.
            forms = cast(
                Iterable[ReaderForm],
                reader.read_file(filename, resolver=runtime.resolve_alias),
            )
            compiler.compile_module(
                forms,
                compiler.CompilerContext(
                    filename=filename, opts=runtime.get_compiler_opts()
                ),
                module,
                collect_bytecode=all_bytecode.append,
            )

        if sys.dont_write_bytecode:
            logger.debug(f"Skipping bytecode generation for '{fullname}'")
            return all_bytecode

        # Cache the bytecode that was collected through the compilation run.
        cache_file_bytes = _basilisp_bytecode(
            path_stats["mtime"], path_stats["size"], all_bytecode
        )
        self._cache_bytecode(filename, cache_filename, cache_file_bytes)
        return all_bytecode

    def _exec_aot_module(
        self,
        fullname: str,
        loader_state: Mapping[str, str],
        module: BasilispModule,
    ) -> list[types.CodeType]:
        """Load and execute a standalone Basilisp AOT artifact."""
        aot_filename = loader_state["aot_filename"]
        source_filename, code = _get_basilisp_aot_bytecode(
            fullname, self.get_data(aot_filename)
        )
        compiler.compile_bytecode(
            code,
            compiler.GeneratorContext(
                filename=source_filename, opts=runtime.get_compiler_opts()
            ),
            compiler.PythonASTOptimizer(),
            module,
        )
        return code

    def exec_module(self, module: types.ModuleType) -> None:
        """Compile the Basilisp module into Python code.

        Basilisp is fundamentally a form-at-a-time compilation, meaning that
        each form in a module may require code compiled from an earlier form, so
        we incrementally compile a Python module by evaluating a single top-level
        form at a time and inserting the resulting AST nodes into the Pyton module."""
        assert isinstance(module, BasilispModule)

        fullname = module.__name__
        if (cached := self._cache.get(fullname)) is None:
            spec = module.__spec__
            assert spec is not None, "Module must have a spec"
            cached = {"spec": spec}
            self._cache[spec.name] = cached
        cached["module"] = module
        spec = cached["spec"]
        filename = spec.loader_state["filename"]

        # During the bootstrapping process, the 'basilisp.core namespace is created with
        # a blank module. If we do not replace the module here with the module we are
        # generating, then we will not be able to use advanced compilation features such
        # as direct Python variable access to functions and other def'ed values.
        if fullname == runtime.CORE_NS:
            ns: runtime.Namespace = runtime.Namespace.get_or_create(runtime.CORE_NS_SYM)
            ns.module = module
            module.__basilisp_namespace__ = ns

        # Set the currently importing module so it can be attached to the namespace when
        # it is created.
        with runtime.bindings(
            {runtime.Var.find_safe(runtime.IMPORT_MODULE_VAR_SYM): module}
        ):

            if "aot_filename" in spec.loader_state:
                cached["bytecode"] = self._exec_aot_module(
                    fullname, spec.loader_state, module
                )
                return

            path_stats = self.path_stats(filename)

            # Check if a valid, cached version of this Basilisp namespace exists and, if so,
            # load it and bypass the expensive compilation process below.
            if os.getenv(_NO_CACHE_ENVVAR, "").lower() == "true":
                cached["bytecode"] = self._exec_module(
                    fullname, spec.loader_state, path_stats, module
                )
            else:
                try:
                    cached["bytecode"] = self._exec_cached_module(
                        fullname, spec.loader_state, path_stats, module
                    )
                except (EOFError, ImportError, OSError) as e:
                    logger.debug(f"Failed to load cached Basilisp module: {e}")
                    cached["bytecode"] = self._exec_module(
                        fullname, spec.loader_state, path_stats, module
                    )

    def compile_namespace(self, ns_name: str) -> str:
        """Compile ``ns_name`` and publish a standalone artifact.

        The namespace is loaded exactly as a normal ``compile`` call would load
        it, then its collected code objects are atomically written beneath the
        currently bound ``basilisp.core/*compile-path*``. The returned string is
        the published artifact path.
        """
        fullname = munge(ns_name)
        compile_path = self._compile_path()
        if compile_path is None:
            raise RuntimeError("basilisp.core/*compile-path* must name a directory")

        with self._aot_lock:
            spec = self.find_spec(fullname, None)
            if spec is None or "aot_filename" in spec.loader_state:
                raise ImportError(f"Could not find Basilisp source for '{ns_name}'")

            if fullname in sys.modules:
                importlib.reload(sys.modules[fullname])
            else:
                importlib.import_module(fullname)

            try:
                code = self._cache[fullname]["bytecode"]
            except KeyError as e:  # pragma: no cover - importlib invariant guard
                raise RuntimeError(f"Could not collect bytecode for '{ns_name}'") from e

            is_package = spec.loader_state["filename"].endswith(
                ("__init__.lpy", "__init__.cljc")
            )
            aot_path = _aot_from_namespace(compile_path, fullname, is_package)
            self._write_aot_bytecode(
                aot_path,
                _basilisp_aot_bytecode(spec.loader_state["filename"], code),
            )
            importlib.invalidate_caches()
            return aot_path


def hook_imports() -> None:
    """Hook into Python's import machinery with a custom Basilisp code
    importer.

    Once this is called, Basilisp code may be called from within Python code
    using standard `import module.submodule` syntax."""
    if any(isinstance(o, BasilispImporter) for o in sys.meta_path):
        return
    sys.meta_path.insert(0, BasilispImporter())


def compile_namespace(ns_name: str) -> str:
    """Compile a Basilisp namespace using the installed Basilisp importer."""
    for finder in sys.meta_path:
        if isinstance(finder, BasilispImporter):
            return finder.compile_namespace(ns_name)
    raise RuntimeError("Basilisp imports have not been initialized")
