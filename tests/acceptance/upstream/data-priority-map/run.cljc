(load-file "tests/acceptance/upstream/data-priority-map/src/acceptance/data_priority_map/workflow.cljc")
(load-file "tests/acceptance/upstream/data-priority-map/test/acceptance/data_priority_map/checks.cljc")

(println
 (pr-str
  (acceptance.data-priority-map.checks/summary)))
