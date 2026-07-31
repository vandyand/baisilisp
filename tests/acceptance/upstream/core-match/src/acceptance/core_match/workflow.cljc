(ns acceptance.core-match.workflow
  (:require [clojure.core.match :refer [match match-let matchm matchv]]))

(def portable-publics
  '[match match-let matchm matchv])

(defn portable-public-summary []
  (into []
        (map (fn [sym]
               [sym (contains? (ns-publics 'clojure.core.match) sym)])
             portable-publics)))

(defn no-match? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn scalar-vector-summary []
  [[:scalar (match 1
              1 :one
              2 :two
              :else :other)]
   [:multi-occurrence (match [1 2 4]
                        [1 2 b] [:first b]
                        [a 2 4] [:second a]
                        :else :bad)]
   [:vector-rest (match [[1 2 3 4]]
                   [[1 2 & tail]] tail
                   :else :bad)]
   [:matchv (matchv :vector [1 2 3]
              [1 a b] [:vector a b]
              :else :bad)]])

(defn map-seq-summary []
  [[:present-nil (match [{:a nil}]
                   [{:a x}] [:present x]
                   :else :bad)]
   [:missing-key (match [{:a nil}]
                   [{:b nil}] :bad
                   :else :missing)]
   [:map-values (matchm [{:kind :point :x 3 :y 4}]
                 [{:kind :point :x x :y y}] [:point x y]
                 :else :bad)]
   [:seq-fixed (match ['(1 2 4)]
                [([1 2 b] :seq)] [:seq b]
                :else :bad)]
   [:seq-rest (match ['(1 2 3)]
               [([1 & r] :seq)] [(vec r) (first r)]
               :else :bad)]
   [:seq-nested-rest (match ['(1 2 3)]
                      [([1 & [2 x]] :seq)] x
                      :else :bad)]])

(defn app-as-let-summary []
  [[:application (match [[1 2 3]]
                  [[1 (3 :<< inc) 3]] :app
                  :else :bad)]
   [:application-map (match [{:a 1 :b 2}]
                       [{:a (2 :<< inc) :b _}] :app-map
                       :else :bad)]
   [:as-pattern (match [[1 2]]
                  [([a b] :as whole)] [a b whole]
                  :else :bad)]
   [:match-let (match-let [value [1 2 3]]
                [[1 x & tail]] [x tail]
                :else :bad)]])

(defn even-integer? [value]
  (and (integer? value) (even? value)))

(defn classify [sample]
  (match [sample]
    [{:kind :point :x x :y y}] [:point x y]
    [{:kind :named :name name :value v}] [:named name v]
    [[a b & tail]] [:vector a b tail]
    [([:node tag & tail] :seq)] [:node tag (vec tail)]
    [nil] :nil
    [(true :<< even-integer?)] :even
    :else (vec (list :literal sample))))

(defn generated-values []
  [{:kind :point :x 1 :y 2}
   {:kind :named :name :alpha :value nil}
   [1 2 3 4]
   [:only-one]
   '(:node :branch 1 2)
   '(:other :branch)
   nil
   42
   41
   :keyword
   {:kind :point :x -1 :y 5}
   [10 20]])

(defn generated-summary []
  (mapv classify (generated-values)))

(defn boundary-summary []
  [[:no-match (no-match? #(match [:unmatched]
                            [:matched] :bad))]
   [:map-missing-nil-distinct (match [{:a nil}]
                                [{:missing _}] :bad
                                [{:a nil}] :present
                                :else :missing)]])
