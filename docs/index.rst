.. Basilisp documentation master file, created by
   sphinx-quickstart on Fri Sep 14 08:39:59 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to BaisiLisp's documentation!
======================================

.. image:: https://img.shields.io/badge/GitHub-baisilisp-green?style=flat-square
   :target: https://github.com/vandyand/baisilisp
   :alt: Link to BaisiLisp GitHub repository
.. image:: https://img.shields.io/pypi/v/baisilisp.svg?style=flat-square
   :target: https://pypi.org/project/baisilisp/
   :alt: Link to BaisiLisp PyPI page for current release; shows the current release version
.. image:: https://img.shields.io/pypi/pyversions/baisilisp.svg?style=flat-square
   :target: https://pypi.org/project/baisilisp/
   :alt: Link to BaisiLisp PyPI page for current release; shows currently supported Python versions
.. image:: https://github.com/vandyand/baisilisp/actions/workflows/run-tests.yml/badge.svg?branch=main&style=flat-square
   :target: https://github.com/vandyand/baisilisp/actions/workflows/run-tests.yml
   :alt: Link to BaisiLisp test CI workflow on GitHub Actions
.. image:: https://github.com/vandyand/baisilisp/actions/workflows/run-clojure-test-suite.yml/badge.svg?branch=main&style=flat-square
   :target: https://github.com/vandyand/baisilisp/actions/workflows/run-clojure-test-suite.yml
   :alt: Link to BaisiLisp Clojure test-suite CI workflow on GitHub Actions
.. image:: https://img.shields.io/github/license/vandyand/baisilisp.svg?style=flat-square
   :target: https://github.com/vandyand/baisilisp/blob/main/LICENSE
   :alt: Link to BaisiLisp license file

BaisiLisp is a compatibility-focused Basilisp fork: a :ref:`Clojure-compatible(-ish) <differences_from_clojure>` Lisp dialect hosted on Python 3 with seamless Python interop.

BaisiLisp compiles down to raw Python 3 code and executes on the Python 3 virtual machine, allowing natural interoperability between existing Python libraries and new Lisp code.

Use the links below to learn more about BaisiLisp and to find help guide you as you are using BaisiLisp.

.. note::

   This documentation strives to be correct and complete, but if you do find a issue, please feel free to `file an issue on GitHub <https://github.com/vandyand/baisilisp/issues>`_.

Contents
--------

.. toctree::
   :maxdepth: 2

   features
   gettingstarted
   differencesfromclojure
   parityroadmap
   parityarchitecture
   paritydecisions
   concepts
   concurrency
   reference
   releasenotes
   contributing

.. toctree::
   :caption: Meta
   :maxdepth: 1

   PyPI <https://pypi.org/project/baisilisp/>
   GitHub <https://github.com/vandyand/baisilisp>

Indices and tables
==================

* :ref:`genindex`
* :ref:`lpy-nsindex`
* :ref:`search`
