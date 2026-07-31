(load-file "tests/acceptance/upstream/tools-logging/src/acceptance/tools_logging/workflow.cljc")
(load-file "tests/acceptance/upstream/tools-logging/test/acceptance/tools_logging/checks.cljc")

(println
 (pr-str
  (acceptance.tools-logging.checks/summary)))
