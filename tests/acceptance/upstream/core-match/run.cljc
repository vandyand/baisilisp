(load-file "tests/acceptance/upstream/core-match/src/acceptance/core_match/workflow.cljc")
(load-file "tests/acceptance/upstream/core-match/test/acceptance/core_match/checks.cljc")

(println
 (pr-str
  (acceptance.core-match.checks/summary)))
