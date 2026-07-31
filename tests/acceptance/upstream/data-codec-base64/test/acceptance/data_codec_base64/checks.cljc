(ns acceptance.data-codec-base64.checks
  (:require [acceptance.data-codec-base64.workflow :as workflow]))

(defn summary []
  [[:publics   (workflow/public-summary)]
   [:lengths   (workflow/length-summary)]
   [:vectors   (workflow/vector-summary)]
   [:offsets   (workflow/offset-summary)]
   [:decoder   (workflow/decoder-boundary-summary)]
   [:transfer  (workflow/transfer-summary)]
   [:generated (workflow/generated-summary)]])
