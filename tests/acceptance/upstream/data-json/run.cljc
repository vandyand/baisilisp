(load-file "tests/acceptance/upstream/data-json/src/acceptance/data_json/workflow.cljc")
(load-file "tests/acceptance/upstream/data-json/test/acceptance/data_json/checks.cljc")

(println
 (pr-str
  (acceptance.data-json.checks/summary)))
