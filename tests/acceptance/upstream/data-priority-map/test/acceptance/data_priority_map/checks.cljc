(ns acceptance.data-priority-map.checks
  (:require [acceptance.data-priority-map.workflow :as workflow]))

(defn summary []
  [[:publics      (workflow/public-summary)]
   [:queue        (workflow/queue-summary)]
   [:ordering     (workflow/ordering-summary)]
   [:bounds       (workflow/bounds-summary)]
   [:constructor  (workflow/constructor-summary)]
   [:updates      (workflow/update-summary)]
   [:boundaries   (workflow/boundary-summary)]
   [:generated    (workflow/generated-summary)]])
