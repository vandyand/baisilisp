# 🐍 BaisiLisp 🐍

A compatibility-focused Basilisp fork: a Clojure-compatible(-ish) Lisp dialect
hosted on Python 3 with seamless Python interop. The installed Python and Lisp
namespace remains ``basilisp`` for source compatibility.

[![PyPI](https://img.shields.io/pypi/v/baisilisp.svg?style=flat-square)](https://pypi.org/project/baisilisp/) [![python](https://img.shields.io/pypi/pyversions/baisilisp.svg?style=flat-square)](https://pypi.org/project/baisilisp/) [![pyimpl](https://img.shields.io/pypi/implementation/baisilisp.svg?style=flat-square)](https://pypi.org/project/baisilisp/) [![Run tests](https://github.com/vandyand/baisilisp/actions/workflows/run-tests.yml/badge.svg?branch=main)](https://github.com/vandyand/baisilisp/actions/workflows/run-tests.yml) [![Run clojure-test-suite](https://github.com/vandyand/baisilisp/actions/workflows/run-clojure-test-suite.yml/badge.svg?branch=main)](https://github.com/vandyand/baisilisp/actions/workflows/run-clojure-test-suite.yml) [![license](https://img.shields.io/github/license/vandyand/baisilisp.svg?style=flat-square)](https://github.com/vandyand/baisilisp/blob/main/LICENSE)

## Getting Started

BaisiLisp is developed on [GitHub](https://github.com/vandyand/baisilisp) and
hosted on [PyPI](https://pypi.org/project/baisilisp/). You can fetch BaisiLisp
using `pip` (or any other Python dependency manager which can pull from PyPI):

```bash
pip install baisilisp
```

Once BaisiLisp is installed, you can enter into the REPL using:

```bash
basilisp repl
```

## Documentation

BaisiLisp documentation is maintained in this repository. It can help guide your
exploration at the REPL and beyond. Additionally, BaisiLisp features many of the
same functions and idioms as [Clojure](https://clojure.org/), so you may find
guides and documentation there helpful for getting started.

For those who prefer a video introduction, feel free to check out this
[talk](https://youtu.be/ruGRHYpq448?si=0jr2a6uWlq6Vi2_k) hosted by the
[London Clojurians](https://www.meetup.com/london-clojurians/) group about Basilisp.

## Contributing

Contributions are welcome. BaisiLisp retains the upstream Eclipse Public License
1.0 and attribution; please file fork-specific issues in this repository.

If you have a question, please use [GitHub Discussions](https://github.com/vandyand/baisilisp/discussions).

## Release channels

Tagged releases are stable versions. Every successful commit to `main` is also
published to PyPI as a development version; install that stream explicitly:

```bash
pip install --pre --upgrade baisilisp
```

The distribution is a drop-in replacement, so do not install it alongside the
upstream `basilisp` distribution in the same environment.

## License

Eclipse Public License 1.0
