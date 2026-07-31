(ns acceptance.tools-reader.checks
  (:require [acceptance.tools-reader.workflow :as workflow]))

(defn summary []
  [[:publics    (workflow/public-summary)]
   [:core-read  (workflow/core-read-summary)]
   [:edn-read   (workflow/edn-read-summary)]
   [:tags       (workflow/tag-summary)]
   [:read-cond  (workflow/read-cond-summary)]
   [:reader-types (workflow/reader-types-summary)]
   [:commons    (workflow/commons-summary)]
   [:defaults   (workflow/default-data-readers-summary)]
   [:errors     (workflow/error-boundary-summary)]
   [:generated  (workflow/generated-summary)]])
