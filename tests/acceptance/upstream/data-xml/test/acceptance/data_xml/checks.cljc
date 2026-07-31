(ns acceptance.data-xml.checks
  (:require [acceptance.data-xml.workflow :as workflow]))

(defn summary []
  [[:publics   (workflow/public-summary)]
   [:qnames    (workflow/qname-summary)]
   [:elements  (workflow/element-summary)]
   [:events    (workflow/event-summary)]
   [:parse     (workflow/parse-emit-summary)]
   [:sexp      (workflow/sexp-summary)]
   [:generated (workflow/generated-summary)]])
