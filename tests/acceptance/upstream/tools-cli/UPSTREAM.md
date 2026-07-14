# clojure/tools.cli Basilisp port

- Upstream: https://github.com/clojure/tools.cli
- Pinned revision: `865e988e6af3b2a7ea7fad218ce2160b72157c27`
- Upstream license: Eclipse Public License 1.0
- Upstream source: `upstream/src/main/clojure/clojure/tools/cli.cljc`
- Basilisp port: `src/basilisp/tools/cli.lpy`

The upstream snapshot is retained unchanged as a Git submodule. The Basilisp
port is a line-preserving derivative with only host-boundary adaptations:

- its namespace is `basilisp.tools.cli`;
- `Throwable` around user-supplied parsing and validation callbacks becomes
  `python/Exception`; `KeyboardInterrupt`, `SystemExit`, and other
  `BaseException` control signals are deliberately not swallowed;
- JVM `String` hints and the legacy Java exception constructor are replaced by
  their Python-neutral equivalents;
- tokenizer predicate checks use Python's `re.search`, preserving the upstream
  branch order while avoiding a compiler direct-linking edge; and
- `clojure.string/triml` and `trimr` are provided by the standard Basilisp
  string port.

The acceptance runner executes the original upstream source under Clojure and
the Basilisp package port under Basilisp, then compares a data-only contract
derived from upstream test cases.
