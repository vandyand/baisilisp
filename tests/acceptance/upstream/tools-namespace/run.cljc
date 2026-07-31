(load-file "tests/acceptance/upstream/tools-namespace/src/acceptance/tools_namespace/workflow.cljc")
(load-file "tests/acceptance/upstream/tools-namespace/test/acceptance/tools_namespace/checks.cljc")

(println
 (pr-str
  (acceptance.tools-namespace.checks/summary)))
