(ns acceptance.core-match.checks
  (:require [acceptance.core-match.workflow :as workflow]))

(defn summary []
  [[:publics       (workflow/portable-public-summary)]
   [:scalar-vector (workflow/scalar-vector-summary)]
   [:map-seq       (workflow/map-seq-summary)]
   [:app-as-let    (workflow/app-as-let-summary)]
   [:generated     (workflow/generated-summary)]
   [:boundaries    (workflow/boundary-summary)]])
