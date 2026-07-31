(load-file "tests/acceptance/upstream/core-async/src/acceptance/core_async/workflow.cljc")
(load-file "tests/acceptance/upstream/core-async/test/acceptance/core_async/checks.cljc")

(println
 (pr-str
  (acceptance.core-async.checks/summary)))
