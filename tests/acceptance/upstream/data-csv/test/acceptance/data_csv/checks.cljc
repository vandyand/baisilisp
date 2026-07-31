(ns acceptance.data-csv.checks
  (:require [acceptance.data-csv.workflow :as workflow]))

(defn summary []
  [[:basic     (workflow/basic-summary)]
   [:options   (workflow/option-summary)]
   [:scalars   (workflow/scalar-summary)]
   [:generated (workflow/generated-summary)]])
