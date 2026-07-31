(ns acceptance.tools-logging.checks
  (:require [acceptance.tools-logging.workflow :as workflow]))

(defn summary []
  [[:publics    (workflow/public-summary)]
   [:factory    (workflow/factory-summary)]
   [:macros     (workflow/macro-gating-summary)]
   [:streams    (workflow/stream-capture-summary)]
   [:readable   (workflow/readable-summary)]
   [:arities    (workflow/arity-summary)]
   [:boundaries (workflow/boundary-summary)]
   [:generated  (workflow/generated-summary)]])
