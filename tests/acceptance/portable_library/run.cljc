;; A library-owned acceptance entrypoint. Source is loaded explicitly so the
;; harness proves a multi-file source tree without Maven or JAR resolution.
(load-file "tests/acceptance/portable_library/src/acceptance/portable_library/util.cljc")
(load-file "tests/acceptance/portable_library/src/acceptance/portable_library/catalog.cljc")
(load-file "tests/acceptance/portable_library/test/acceptance/portable_library/checks.cljc")

(println (pr-str (acceptance.portable-library.checks/acceptance-summary)))
