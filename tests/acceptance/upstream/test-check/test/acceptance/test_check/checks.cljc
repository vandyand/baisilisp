(ns acceptance.test-check.checks
  (:require [acceptance.test-check.workflow :as workflow]))

(defn summary []
  [[:publics     (workflow/public-summary)]
   [:primitives  (workflow/primitive-generator-summary)]
   [:collections (workflow/collection-generator-summary)]
   [:combinators (workflow/combinator-summary)]
   [:random-rose (workflow/random-rose-summary)]
   [:properties  (workflow/property-summary)]
   [:clojure-test (workflow/clojure-test-summary)]
   [:generated   (workflow/generated-summary)]])
