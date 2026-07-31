(ns acceptance.tools-namespace.checks
  (:require [acceptance.tools-namespace.workflow :as workflow]))

(defn summary []
  [[:publics       (workflow/public-summary)]
   [:parse         (workflow/parse-summary)]
   [:dependency    (workflow/dependency-summary)]
   [:generated     (workflow/generated-graph-summary)]
   [:source        (workflow/source-discovery-summary)]
   [:move          (workflow/move-summary)]])
