(load-file "tests/acceptance/upstream/test-check/src/acceptance/test_check/workflow.cljc")
(load-file "tests/acceptance/upstream/test-check/test/acceptance/test_check/checks.cljc")

(println
 (pr-str
  (acceptance.test-check.checks/summary)))
