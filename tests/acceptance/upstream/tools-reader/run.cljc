(load-file "tests/acceptance/upstream/tools-reader/src/acceptance/tools_reader/workflow.cljc")
(load-file "tests/acceptance/upstream/tools-reader/test/acceptance/tools_reader/checks.cljc")

(println
 (pr-str
  (acceptance.tools-reader.checks/summary)))
