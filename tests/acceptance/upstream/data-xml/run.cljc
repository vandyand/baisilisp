(load-file "tests/acceptance/upstream/data-xml/src/acceptance/data_xml/workflow.cljc")
(load-file "tests/acceptance/upstream/data-xml/test/acceptance/data_xml/checks.cljc")

(println
 (pr-str
  (acceptance.data-xml.checks/summary)))
