(ns acceptance.data-json.checks
  (:require [acceptance.data-json.workflow :as workflow]))

(defn summary []
  [[:publics    (workflow/public-summary)]
   [:defaults   (workflow/default-options-summary)]
   [:read       (workflow/read-summary)]
   [:write      (workflow/write-summary)]
   [:callbacks  (workflow/callback-summary)]
   [:boundaries (workflow/boundary-summary)]
   [:protocol   (workflow/protocol-summary)]
   [:generated  (workflow/generated-summary)]])
