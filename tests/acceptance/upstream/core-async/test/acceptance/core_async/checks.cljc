(ns acceptance.core-async.checks
  (:require [acceptance.core-async.workflow :as workflow]))

(defn summary []
  (let [go-transform (workflow/go-transform-summary)
        selection    (workflow/selection-summary)
        pipeline     (workflow/pipeline-summary)
        collection   (workflow/collection-summary)
        routing      (workflow/routing-summary)
        stress       (workflow/stress-summary)]
    [[:go-transform go-transform]
     [:selection    selection]
     [:pipeline     pipeline]
     [:collection   collection]
     [:routing      routing]
     [:stress       stress]]))
