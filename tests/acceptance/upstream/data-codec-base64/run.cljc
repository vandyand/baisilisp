(load-file "tests/acceptance/upstream/data-codec-base64/src/acceptance/data_codec_base64/workflow.cljc")
(load-file "tests/acceptance/upstream/data-codec-base64/test/acceptance/data_codec_base64/checks.cljc")

(println
 (pr-str
  (acceptance.data-codec-base64.checks/summary)))
