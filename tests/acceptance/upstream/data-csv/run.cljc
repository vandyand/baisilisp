(load-file "tests/acceptance/upstream/data-csv/src/acceptance/data_csv/workflow.cljc")
(load-file "tests/acceptance/upstream/data-csv/test/acceptance/data_csv/checks.cljc")

(println
 (pr-str
  (acceptance.data-csv.checks/summary)))
