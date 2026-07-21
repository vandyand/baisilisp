"""The small Python kernel behind the portable ``basilisp.test.check`` API.

The public API deliberately lives in ``.lpy`` files.  Keeping the generator
kernel in Python makes RNG state and a (potentially very deep) shrink tree
ordinary immutable Python objects, while generated values remain Basilisp
persistent collections.
"""

from __future__ import annotations

import math
import time
import uuid as _uuid
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from basilisp.lang import keyword as kw
from basilisp.lang import list as llist
from basilisp.lang import map as lmap
from basilisp.lang import set as lset
from basilisp.lang import symbol as sym
from basilisp.lang import vector as lvec


def _k(name: str, ns: str | None = None):
    return kw.keyword(name, ns=ns)


K_RESULT = _k("result")
K_ARGS = _k("args")
K_PASS = _k("pass?")
K_NUM_TESTS = _k("num-tests")
K_SEED = _k("seed")
K_FAIL = _k("fail")
K_SHRUNK = _k("shrunk")


_MASK64 = (1 << 64) - 1


def _mix64(value: int) -> int:
    value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9 & _MASK64
    value = (value ^ (value >> 27)) * 0x94D049BB133111EB & _MASK64
    return (value ^ (value >> 31)) & _MASK64


@dataclass(frozen=True, slots=True)
class RNG:
    """A pure splittable 64-bit RNG.

    It is intentionally immutable: consuming a generator happens through
    ``split`` rather than mutating shared global random state, which is the
    key reproducibility contract of test.check.
    """

    state: int

    def rand_long(self) -> int:
        result = _mix64((self.state + 0x9E3779B97F4A7C15) & _MASK64)
        return result - (1 << 64) if result & (1 << 63) else result

    def rand_double(self) -> float:
        return (_mix64((self.state + 0x9E3779B97F4A7C15) & _MASK64) >> 11) * (
            1.0 / (1 << 53)
        )

    def split(self) -> tuple["RNG", "RNG"]:
        left = _mix64((self.state + 0x9E3779B97F4A7C15) & _MASK64)
        right = _mix64((self.state + 0xD1B54A32D192ED03) & _MASK64)
        return RNG(left), RNG(right)

    def split_n(self, n: int) -> tuple["RNG", ...]:
        if n < 0:
            raise ValueError("n must not be negative")
        result: list[RNG] = []
        current = self
        for _ in range(n):
            first, current = current.split()
            result.append(first)
        return tuple(result)


def make_random(seed: int | None = None) -> RNG:
    if seed is None:
        seed = time.time_ns()
    return RNG(int(seed) & _MASK64)


def rand_long(rng: RNG) -> int:
    return rng.rand_long()


def rand_double(rng: RNG) -> float:
    return rng.rand_double()


def split(rng: RNG):
    return lvec.vector(rng.split())


def split_n(rng: RNG, n: int):
    return lvec.vector(rng.split_n(n))


@dataclass(frozen=True, slots=True)
class RoseTree:
    root: Any
    children: tuple["RoseTree", ...] = ()


def make_rose(root: Any, children: Iterable[RoseTree] = ()) -> RoseTree:
    return RoseTree(root, tuple(children))


def root(tree: RoseTree) -> Any:
    return tree.root


def children(tree: RoseTree):
    return lvec.vector(tree.children)


def rose_pure(value: Any) -> RoseTree:
    return RoseTree(value)


def rose_fmap(f: Callable[[Any], Any], tree: RoseTree) -> RoseTree:
    return RoseTree(f(tree.root), tuple(rose_fmap(f, child) for child in tree.children))


def rose_join(tree: RoseTree) -> RoseTree:
    inner: RoseTree = tree.root
    return RoseTree(
        inner.root,
        tuple(rose_join(child) for child in tree.children) + inner.children,
    )


def rose_bind(tree: RoseTree, f: Callable[[Any], RoseTree]) -> RoseTree:
    return rose_join(rose_fmap(f, tree))


def rose_filter(pred: Callable[[Any], bool], tree: RoseTree) -> RoseTree:
    return RoseTree(
        tree.root,
        tuple(rose_filter(pred, child) for child in tree.children if pred(child.root)),
    )


def _collection_shrinks(
    values: Sequence[RoseTree], factory: Callable[[Iterable[Any]], Any]
):
    """Immediate collection shrinks.

    Clojure's implementation keeps this tree lazy.  Eagerly constructing all
    descendants turns a 60-element vector into an exponential allocation, so
    retain the same first shrink frontier here and let a later generated trial
    provide further structure when needed.
    """
    result: list[RoseTree] = []
    if values:
        result.append(RoseTree(factory(())))
    if len(values) >= 4:
        half = len(values) // 2
        result.append(RoseTree(factory(v.root for v in values[:half])))
        result.append(RoseTree(factory(v.root for v in values[half:])))
    for index, value in enumerate(values):
        result.append(
            RoseTree(factory(v.root for v in values[:index] + values[index + 1 :]))
        )
        for child in value.children:
            copy = list(values)
            copy[index] = child
            result.append(RoseTree(factory(v.root for v in copy)))
    return tuple(result)


def _rose_collection(
    values: Sequence[RoseTree], factory: Callable[[Iterable[Any]], Any]
) -> RoseTree:
    return RoseTree(
        factory(v.root for v in values), _collection_shrinks(values, factory)
    )


class Generator:
    __slots__ = ("gen",)

    def __init__(self, gen: Callable[[RNG, int], RoseTree]):
        self.gen = gen


def generator_q(value: Any) -> bool:
    return isinstance(value, Generator)


def call_gen(generator: Generator, rng: RNG, size: int) -> RoseTree:
    if not isinstance(generator, Generator):
        raise TypeError("Expected a test.check generator")
    return generator.gen(rng, max(0, int(size)))


def gen_pure(value: Any) -> Generator:
    return Generator(
        lambda _rng, _size: value if isinstance(value, RoseTree) else rose_pure(value)
    )


def gen_fmap(f: Callable[[Any], Any], generator: Generator) -> Generator:
    return Generator(lambda rng, size: f(call_gen(generator, rng, size)))


def gen_bind(generator: Generator, f: Callable[[RoseTree], Generator]) -> Generator:
    def produce(rng: RNG, size: int) -> RoseTree:
        r1, r2 = rng.split()
        return call_gen(f(call_gen(generator, r1, size)), r2, size)

    return Generator(produce)


def fmap(f: Callable[[Any], Any], generator: Generator) -> Generator:
    if not generator_q(generator):
        raise TypeError("Second arg to fmap must be a generator")
    return Generator(lambda rng, size: rose_fmap(f, call_gen(generator, rng, size)))


def return_(value: Any) -> Generator:
    return Generator(lambda _rng, _size: rose_pure(value))


def bind(generator: Generator, f: Callable[[Any], Generator]) -> Generator:
    if not generator_q(generator):
        raise TypeError("First arg to bind must be a generator")

    def produce(rng: RNG, size: int) -> RoseTree:
        outer = call_gen(generator, rng, size)
        inner = f(outer.root)
        if not generator_q(inner):
            raise TypeError("Function passed to bind must return a generator")
        value = call_gen(inner, rng.split()[1], size)
        return rose_join(
            rose_fmap(lambda item: call_gen(f(item), rng.split()[1], size), outer)
        )

    return Generator(produce)


def make_size_range_seq(max_size: int):
    max_size = max(1, int(max_size))
    while True:
        yield from range(max_size)


def sample_seq(generator: Generator, max_size: int = 200):
    rng = make_random(0xC10C10)
    for size in make_size_range_seq(max_size):
        left, rng = rng.split()
        yield call_gen(generator, left, size).root


def sample(generator: Generator, num_samples: int = 10):
    return lvec.vector(
        value for _, value in zip(range(num_samples), sample_seq(generator))
    )


def generate(generator: Generator, size: int = 30, seed: int | None = None):
    return call_gen(generator, make_random(seed), size).root


def _integer_tree(
    value: int, lower: int | None = None, upper: int | None = None
) -> RoseTree:
    # A single recursive path retains the essential invariant (counterexamples
    # move monotonically toward the simplest in-range value) without eagerly
    # materialising the exponential tree that a lazy Clojure sequence normally
    # hides.  The direct bound is tried first, then bisection.
    target = lower if lower is not None else 0
    if value == target:
        return RoseTree(value)
    middle = target + int((value - target) / 2)
    direct = RoseTree(target)
    if middle == target:
        return RoseTree(value, (direct,))
    return RoseTree(value, (direct, _integer_tree(middle, lower, upper)))


def sized(f: Callable[[int], Generator]) -> Generator:
    return Generator(lambda rng, size: call_gen(f(size), rng, size))


def resize(size: int, generator: Generator) -> Generator:
    return Generator(lambda rng, _old: call_gen(generator, rng, size))


def scale(f: Callable[[int], int], generator: Generator) -> Generator:
    return sized(lambda size: resize(f(size), generator))


def choose(lower: int, upper: int) -> Generator:
    lower, upper = int(lower), int(upper)
    if lower > upper:
        raise ValueError("lower must not exceed upper")

    def produce(rng: RNG, _size: int):
        value = lower + int(rng.rand_double() * (upper - lower + 1))
        return _integer_tree(min(upper, value), lower, upper)

    return Generator(produce)


def one_of(generators: Iterable[Generator]) -> Generator:
    generators = tuple(generators)
    if not generators or not all(generator_q(g) for g in generators):
        raise ValueError("one-of requires one or more generators")
    return bind(choose(0, len(generators) - 1), lambda index: generators[index])


def frequency(pairs: Iterable[Sequence[Any]]) -> Generator:
    pairs = tuple(
        (int(weight), generator) for weight, generator in pairs if int(weight) > 0
    )
    if not pairs or not all(generator_q(generator) for _, generator in pairs):
        raise ValueError("frequency requires positive weighted generators")
    total = sum(weight for weight, _ in pairs)

    def pick(value: int) -> Generator:
        for weight, generator in pairs:
            if value < weight:
                return generator
            value -= weight
        return pairs[-1][1]

    return bind(choose(0, total - 1), pick)


def elements(coll: Iterable[Any]) -> Generator:
    values = tuple(coll)
    if not values:
        raise ValueError("elements cannot be called with an empty collection")
    return fmap(lambda index: values[index], choose(0, len(values) - 1))


def such_that(
    pred: Callable[[Any], bool], generator: Generator, opts: Any = 10
) -> Generator:
    if isinstance(opts, int):
        max_tries = opts
    else:
        max_tries = int(_options(opts).get("max-tries", 10))

    def produce(rng: RNG, size: int) -> RoseTree:
        for _ in range(max_tries):
            left, rng = rng.split()
            tree = call_gen(generator, left, size)
            if pred(tree.root):
                return rose_filter(pred, tree)
            size += 1
        raise ValueError(
            f"Couldn't satisfy such-that predicate after {max_tries} tries."
        )

    return Generator(produce)


def not_empty(generator: Generator) -> Generator:
    return such_that(bool, generator)


def no_shrink(generator: Generator) -> Generator:
    return Generator(lambda rng, size: RoseTree(call_gen(generator, rng, size).root))


def shrink_2(generator: Generator) -> Generator:
    return generator


def tuple_gen(*generators: Generator) -> Generator:
    if not all(generator_q(g) for g in generators):
        raise TypeError("Arguments to tuple must be generators")

    def produce(rng: RNG, size: int):
        trees = tuple(
            call_gen(g, state, size)
            for g, state in zip(generators, rng.split_n(len(generators)))
        )

        # Unlike a generated collection, tuple has a fixed arity. Removing an
        # element would make a property function receive the wrong number of
        # arguments during shrinking.  Keep one immediate shrink per member,
        # but do not recursively build every combination of member shrink
        # trees: two 64-bit integer generators otherwise materialize an
        # exponential tree before the property can run at all.
        children: list[RoseTree] = []
        for index, item in enumerate(trees):
            for child in item.children:
                roots = [tree.root for tree in trees]
                roots[index] = child.root
                children.append(RoseTree(lvec.vector(roots)))
        return RoseTree(lvec.vector(tree.root for tree in trees), tuple(children))

    return Generator(produce)


def vector(
    generator: Generator,
    min_elements: int | None = None,
    max_elements: int | None = None,
) -> Generator:
    if min_elements is not None and max_elements is None:
        max_elements = min_elements

    def produce(rng: RNG, size: int):
        low = 0 if min_elements is None else min_elements
        high = size if max_elements is None else max_elements
        count = generate(choose(low, max(low, high)), size, rng.rand_long())
        trees = tuple(call_gen(generator, state, size) for state in rng.split_n(count))
        return _rose_collection(trees, lvec.vector)

    return Generator(produce)


def list_gen(generator: Generator) -> Generator:
    return fmap(lambda values: llist.list(values), vector(generator))


def shuffle(coll: Iterable[Any]) -> Generator:
    values = lvec.vector(coll)

    def produce(rng: RNG, _size: int):
        result = list(values)
        current = rng
        for index in range(len(result) - 1, 0, -1):
            left, current = current.split()
            swap_index = int(left.rand_double() * (index + 1))
            result[index], result[swap_index] = result[swap_index], result[index]
        return RoseTree(lvec.vector(result), (RoseTree(values),))

    return Generator(produce)


def hash_map(*kvs: Any) -> Generator:
    if len(kvs) % 2:
        raise ValueError("hash-map needs an even number of arguments")
    keys, generators = kvs[::2], kvs[1::2]
    return fmap(
        lambda values: lmap.map(dict(zip(keys, values))), tuple_gen(*generators)
    )


def _distinct(
    generator: Generator,
    factory: Callable[[Iterable[Any]], Any],
    opts: Any = None,
    key: Callable[[Any], Any] = lambda value: value,
) -> Generator:
    options = _options(opts)
    fixed = options.get("num-elements")
    minimum = int(options.get("min-elements", 0 if fixed is None else fixed))
    maximum = int(options.get("max-elements", fixed if fixed is not None else -1))
    tries = int(options.get("max-tries", 10))

    def produce(rng: RNG, size: int):
        target = (
            int(fixed)
            if fixed is not None
            else int(
                generate(
                    choose(minimum, max(minimum, size if maximum < 0 else maximum)),
                    size,
                    rng.rand_long(),
                )
            )
        )
        values: list[RoseTree] = []
        seen: set[Any] = set()
        for state in rng.split_n(max(tries, target) * max(1, target)):
            value = call_gen(generator, state, size)
            marker = key(value.root)
            if marker not in seen:
                values.append(value)
                seen.add(marker)
                if len(values) == target:
                    break
        if len(values) < minimum:
            raise ValueError("Couldn't generate enough distinct values")
        return _rose_collection(tuple(values), factory)

    return Generator(produce)


def vector_distinct(generator: Generator, opts: Any = None) -> Generator:
    return _distinct(generator, lvec.vector, opts)


def list_distinct(generator: Generator, opts: Any = None) -> Generator:
    return _distinct(generator, llist.list, opts)


def vector_distinct_by(
    key: Callable[[Any], Any], generator: Generator, opts: Any = None
) -> Generator:
    return _distinct(generator, lvec.vector, opts, key)


def list_distinct_by(
    key: Callable[[Any], Any], generator: Generator, opts: Any = None
) -> Generator:
    return _distinct(generator, llist.list, opts, key)


def set_gen(generator: Generator, opts: Any = None) -> Generator:
    return _distinct(generator, lset.set, opts)


def sorted_set(generator: Generator, opts: Any = None) -> Generator:
    return _distinct(generator, lset.set, opts)


def map_gen(key_gen: Generator, value_gen: Generator, opts: Any = None) -> Generator:
    return fmap(
        lambda pairs: lmap.map(dict(pairs)),
        _distinct(
            tuple_gen(key_gen, value_gen), lvec.vector, opts, lambda pair: pair[0]
        ),
    )


def large_integer_star(opts: Any = None) -> Generator:
    options = _options(opts)
    return choose(
        int(options.get("min", -(1 << 63))), int(options.get("max", (1 << 63) - 1))
    )


def double_star(opts: Any = None) -> Generator:
    options = _options(opts)
    lower = float(options.get("min", -1.0e100))
    upper = float(options.get("max", 1.0e100))

    def finite_value(rng: RNG, _size: int) -> RoseTree:
        value = lower + (rng.rand_double() * (upper - lower))
        # Explicit extreme bounds can overflow when subtracted. Clamp so a
        # finite-only generator cannot accidentally yield infinity or NaN.
        if not math.isfinite(value):
            value = lower if rng.rand_double() < 0.5 else upper
        return RoseTree(value)

    finite = Generator(finite_value)
    choices: list[tuple[int, Generator]] = [(96, finite), (2, return_(0.0))]
    if options.get("infinite?", True):
        if "max" not in options:
            choices.append((1, return_(math.inf)))
        if "min" not in options:
            choices.append((1, return_(-math.inf)))
    if options.get("NaN?", True):
        choices.append((1, return_(math.nan)))
    return frequency(choices)


def _char(lower: int, upper: int) -> Generator:
    return fmap(chr, choose(lower, upper))


def _string(char_gen: Generator) -> Generator:
    return fmap(lambda chars: "".join(chars), vector(char_gen))


def recursive_gen(
    container_fn: Callable[[Generator], Generator], scalar: Generator
) -> Generator:
    def build(size: int) -> Generator:
        if size <= 1:
            return scalar
        return frequency(
            (
                (3, resize(max(0, size // 2), scalar)),
                (7, resize(max(0, size // 2), container_fn(build(size // 2)))),
            )
        )

    return sized(build)


def container_type(inner: Generator) -> Generator:
    return one_of(
        (vector(inner), list_gen(inner), set_gen(inner), map_gen(inner, inner))
    )


def _options(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        items = value.items()
    else:
        try:
            items = value.items()
        except AttributeError:
            return {}
    result = {}
    for key, item in items:
        result[getattr(key, "name", str(key).lstrip(":"))] = item
    return result


class ErrorResult:
    __slots__ = ("error",)

    def __init__(self, error: BaseException):
        self.error = error


def for_all_star(
    generators: Iterable[Generator], function: Callable[..., Any]
) -> Generator:
    generators = tuple(generators)

    def apply_values(values: Any):
        try:
            result = function(*values)
            if isinstance(result, BaseException):
                result = ErrorResult(result)
        except BaseException as error:  # property exceptions are failures
            result = ErrorResult(error)
        return lmap.map({K_RESULT: result, K_ARGS: lvec.vector(values)})

    return fmap(apply_values, tuple_gen(*generators))


def pass_q(result: Any) -> bool:
    return not isinstance(result, ErrorResult) and bool(result)


def result_data(result: Any):
    if isinstance(result, ErrorResult):
        return lmap.map({_k("error", "basilisp.test.check.properties"): result.error})
    return None


def quick_check(num_tests: int, property_: Generator, *args: Any, **options: Any):
    """Run a property, accepting Clojure's alternating keyword/value options."""
    if args:
        if len(args) == 1 and isinstance(args[0], Mapping):
            options.update(_options(args[0]))
        elif len(args) % 2 == 0:
            options.update(_options(dict(zip(args[::2], args[1::2]))))
        else:
            raise TypeError("quick-check options must be keyword/value pairs")
    options = _options(options)
    seed = options.get("seed")
    actual_seed = int(time.time_ns() if seed is None else seed)
    rng = make_random(actual_seed)
    max_size = max(1, int(options.get("max-size", 200)))
    reporter = options.get("reporter-fn", lambda _event: None)
    started = time.monotonic_ns()
    for trial in range(1, int(num_tests) + 1):
        left, rng = rng.split()
        size = (trial - 1) % max_size
        property_tree = call_gen(property_, left, size)
        result_map = property_tree.root
        result = result_map[K_RESULT]
        args = result_map[K_ARGS]
        if pass_q(result):
            reporter(
                lmap.map(
                    {
                        _k("type"): _k("trial"),
                        K_ARGS: args,
                        K_NUM_TESTS: trial,
                        _k("num-tests-total"): num_tests,
                        K_PASS: True,
                        K_SEED: actual_seed,
                    }
                )
            )
            continue
        shrunk, visited, depth = _shrink(property_tree)
        shrink = lmap.map(
            {
                _k("smallest"): shrunk[K_ARGS],
                _k("depth"): depth,
                _k("total-nodes-visited"): visited,
                K_PASS: False,
                K_RESULT: shrunk[K_RESULT],
                _k("result-data"): result_data(shrunk[K_RESULT]),
                _k("time-shrinking-ms"): 0,
            }
        )
        failure = lmap.map(
            {
                K_FAIL: args,
                _k("failing-size"): size,
                K_NUM_TESTS: trial,
                K_PASS: False,
                K_RESULT: result,
                _k("result-data"): result_data(result),
                K_SEED: actual_seed,
                K_SHRUNK: shrink,
                _k("failed-after-ms"): (time.monotonic_ns() - started) // 1_000_000,
            }
        )
        reporter(lmap.map({_k("type"): _k("failure"), **dict(failure.items())}))
        return failure
    elapsed = (time.monotonic_ns() - started) // 1_000_000
    complete = lmap.map(
        {
            K_RESULT: True,
            K_PASS: True,
            K_NUM_TESTS: int(num_tests),
            _k("time-elapsed-ms"): elapsed,
            K_SEED: actual_seed,
        }
    )
    reporter(lmap.map({_k("type"): _k("complete"), **dict(complete.items())}))
    return complete


def _shrink(failing: RoseTree):
    """Find the deepest left-most counterexample in a property shrink tree."""
    current = failing
    visited = depth = 0
    nodes = list(current.children)
    while nodes:
        node = nodes.pop(0)
        visited += 1
        if pass_q(node.root[K_RESULT]):
            continue
        current = node
        if node.children:
            depth += 1
            nodes = list(node.children)
    return current.root, visited, depth


# Public generator values are initialized after all combinators exist.
boolean = elements((False, True))
nat = sized(lambda size: choose(0, size))
small_integer = sized(lambda size: choose(-size, size))
integer = small_integer
pos_int = nat
neg_int = fmap(lambda value: -value, nat)
s_pos_int = fmap(lambda value: value + 1, nat)
s_neg_int = fmap(lambda value: value - 1, neg_int)
large_integer = large_integer_star()
double = double_star()
char = _char(0, 255)
char_ascii = _char(32, 126)
char_alphanumeric = one_of((_char(48, 57), _char(65, 90), _char(97, 122)))
char_alpha = one_of((_char(65, 90), _char(97, 122)))
string = _string(char)
string_ascii = _string(char_ascii)
string_alphanumeric = _string(char_alphanumeric)
# Clojure's ``bytes`` generator yields a byte array.  ``bytearray`` is the
# corresponding mutable byte-array representation in Basilisp (and the type
# recognized by core/bytes?).
bytes = fmap(lambda values: bytearray(values), vector(choose(0, 255)))
keyword = fmap(lambda value: kw.keyword(value or "x"), string_alphanumeric)
keyword_ns = fmap(
    lambda pair: kw.keyword(pair[1] or "x", ns=pair[0] or "ns"),
    tuple_gen(string_alphanumeric, string_alphanumeric),
)
symbol = fmap(lambda value: sym.symbol(value or "x"), string_alphanumeric)
symbol_ns = fmap(
    lambda pair: sym.symbol(pair[1] or "x", ns=pair[0] or "ns"),
    tuple_gen(string_alphanumeric, string_alphanumeric),
)
ratio = fmap(
    lambda pair: pair[0] / pair[1], tuple_gen(small_integer, fmap(lambda x: x + 1, nat))
)
uuid = no_shrink(
    fmap(lambda value: _uuid.UUID(int=value & ((1 << 128) - 1)), large_integer)
)
simple_type = one_of(
    (small_integer, double, char, string, ratio, boolean, keyword, symbol, uuid)
)
simple_type_printable = one_of(
    (
        small_integer,
        double,
        char_ascii,
        string_ascii,
        ratio,
        boolean,
        keyword,
        symbol,
        uuid,
    )
)
simple_type_equatable = simple_type
simple_type_printable_equatable = simple_type_printable
any = recursive_gen(container_type, simple_type)
any_printable = recursive_gen(container_type, simple_type_printable)
any_equatable = recursive_gen(container_type, simple_type_equatable)
any_printable_equatable = recursive_gen(container_type, simple_type_printable_equatable)
