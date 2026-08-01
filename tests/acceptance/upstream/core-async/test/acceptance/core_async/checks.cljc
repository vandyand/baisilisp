(ns acceptance.core-async.checks
  (:require [acceptance.core-async.workflow :as workflow]))

(defn summary []
  (let [surface      (workflow/public-surface-summary)
        ioc-alts     (workflow/ioc-alts-summary)
        ioc-helpers  (workflow/ioc-helper-summary)
        go-transform (workflow/go-transform-summary)
        selection    (workflow/selection-summary)
        pipeline     (workflow/pipeline-summary)
        collection   (workflow/collection-summary)
        routing      (workflow/routing-summary)
        stress       (workflow/stress-summary)
        parking      (workflow/parking-boundary-summary)]
    [[:public-surface surface]
     [:ioc-alts     ioc-alts]
     [:ioc-helpers  ioc-helpers]
     [:go-transform go-transform]
     [:selection    selection]
     [:pipeline     pipeline]
     [:collection   collection]
     [:routing      routing]
     [:stress       stress]
     [:parking      parking]]))
